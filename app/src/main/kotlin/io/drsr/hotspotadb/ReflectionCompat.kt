package io.drsr.hotspotadb

import android.util.Log
import io.github.libxposed.api.XposedModule
import java.lang.reflect.Constructor
import java.lang.reflect.Field
import java.lang.reflect.Method
import java.util.ArrayDeque

object ReflectionCompat {
    private const val TAG = HotspotAdbModule.TAG
    private const val ASSIGNABLE_SCORE_BASE = 10
    private const val NULL_ARGUMENT_SCORE = 100
    private const val SYNTHETIC_METHOD_PENALTY = 1_000

    private data class MethodCandidate(
        val method: Method,
        val score: Int,
    )

    fun findFirstClass(
        classLoader: ClassLoader,
        module: XposedModule,
        label: String,
        vararg names: String,
    ): Class<*>? {
        names.forEachIndexed { index, name ->
            val clazz = tryFindClass(name, classLoader)
            if (clazz != null) {
                module.log(Log.INFO, TAG, "HotspotAdb: $label class selected [${index + 1}/${names.size}]: $name")
                return clazz
            }
            module.log(Log.DEBUG, TAG, "HotspotAdb: $label class candidate absent: $name")
        }
        module.log(Log.WARN, TAG, "HotspotAdb: $label class not found in ${names.size} candidate(s)")
        return null
    }

    fun findMethod(
        clazz: Class<*>,
        module: XposedModule,
        label: String,
        name: String,
        includeInherited: Boolean,
        vararg params: Class<*>,
    ): Method? {
        // Walk hierarchy with getDeclaredMethod so protected/package-private methods in
        // superclasses are reachable, unlike getMethod() which only surfaces public methods.
        var cls: Class<*> = clazz
        while (true) {
            val method = runCatching { cls.getDeclaredMethod(name, *params).also { it.isAccessible = true } }.getOrNull()
            if (method != null) {
                val origin = if (cls == clazz) "declared" else "inherited from ${cls.name}"
                module.log(Log.INFO, TAG, "HotspotAdb: $label method selected ($origin): ${method.toGenericString()}")
                return method
            }
            if (!includeInherited) break
            cls = cls.superclass ?: break
        }
        module.log(Log.WARN, TAG, "HotspotAdb: $label method missing: ${clazz.name}#$name(${params.joinToString { it.simpleName }})")
        return null
    }

    fun findConstructor(
        clazz: Class<*>,
        module: XposedModule,
        label: String,
        vararg params: Class<*>,
    ): Constructor<*>? {
        val ctor = runCatching { clazz.getDeclaredConstructor(*params).also { it.isAccessible = true } }.getOrNull()
        if (ctor != null) {
            module.log(Log.INFO, TAG, "HotspotAdb: $label constructor selected: ${ctor.toGenericString()}")
            return ctor
        }
        module.log(Log.DEBUG, TAG, "HotspotAdb: $label constructor missing: ${clazz.name}(${params.joinToString { it.simpleName }})")
        return null
    }

    fun getFieldValueByName(
        obj: Any,
        name: String,
    ): Any? {
        var cls: Class<*>? = obj.javaClass
        while (cls != null && cls != Any::class.java) {
            val field = runCatching { cls.getDeclaredField(name).also { it.isAccessible = true } }.getOrNull()
            if (field != null) return field.get(obj)
            cls = cls.superclass
        }
        return null
    }

    fun getFieldValueByType(
        obj: Any,
        typeName: String,
    ): Any? {
        var cls: Class<*>? = obj.javaClass
        while (cls != null && cls != Any::class.java) {
            val field = cls.declaredFields.firstOrNull { it.type.name == typeName }?.also { it.isAccessible = true }
            if (field != null) return field.get(obj)
            cls = cls.superclass
        }
        return null
    }

    fun getFieldByNamesOrTypes(
        obj: Any,
        names: List<String>,
        typeNames: List<String>,
    ): Field? {
        // Probe in caller-specified order: names take priority over type names.
        // Within each superclass level, try every requested name before any type name so the
        // lookup is deterministic regardless of getDeclaredFields() ordering.
        var cls: Class<*>? = obj.javaClass
        while (cls != null && cls != Any::class.java) {
            val declaredFields = cls.declaredFields
            for (targetName in names) {
                val field = declaredFields.firstOrNull { it.name == targetName }
                if (field != null) {
                    field.isAccessible = true
                    return field
                }
            }
            for (targetType in typeNames) {
                val field = declaredFields.firstOrNull { it.type.name == targetType }
                if (field != null) {
                    field.isAccessible = true
                    return field
                }
            }
            cls = cls.superclass
        }
        return null
    }

    fun tryFindClass(
        name: String,
        classLoader: ClassLoader,
    ): Class<*>? =
        try {
            Class.forName(name, false, classLoader)
        } catch (_: ClassNotFoundException) {
            null
        }

    /**
     * Selects a public method compatible with runtime arguments.
     *
     * Exact reference and boxed-to-primitive matches win over assignable supertypes. Null only
     * matches reference parameters. Stable signature ordering removes dependence on the JVM's
     * unspecified [Class.getMethods] array order.
     */
    internal fun findCompatibleMethod(
        clazz: Class<*>,
        name: String,
        args: Array<out Any?>,
    ): Method? =
        clazz.methods
            .asSequence()
            .filter { it.name == name && it.parameterCount == args.size }
            .mapNotNull { method ->
                var score = 0
                for (index in args.indices) {
                    val argumentScore = compatibilityScore(method.parameterTypes[index], args[index]) ?: return@mapNotNull null
                    score += argumentScore
                }
                if (method.isBridge || method.isSynthetic) score += SYNTHETIC_METHOD_PENALTY
                MethodCandidate(method, score)
            }.sortedWith(
                compareBy<MethodCandidate> { it.score }
                    .thenBy { it.method.toGenericString() },
            ).firstOrNull()
            ?.method

    private fun compatibilityScore(
        parameter: Class<*>,
        argument: Any?,
    ): Int? {
        if (argument == null) return if (parameter.isPrimitive) null else NULL_ARGUMENT_SCORE

        val argumentType = argument.javaClass
        if (parameter == argumentType || primitiveWrapper(parameter) == argumentType) return 0
        if (!parameter.isAssignableFrom(argumentType)) return null
        return ASSIGNABLE_SCORE_BASE + inheritanceDistance(argumentType, parameter)
    }

    private fun primitiveWrapper(primitive: Class<*>): Class<*>? =
        when (primitive) {
            Boolean::class.javaPrimitiveType -> Boolean::class.java
            Byte::class.javaPrimitiveType -> Byte::class.java
            Short::class.javaPrimitiveType -> Short::class.java
            Char::class.javaPrimitiveType -> Char::class.java
            Int::class.javaPrimitiveType -> Int::class.java
            Long::class.javaPrimitiveType -> Long::class.java
            Float::class.javaPrimitiveType -> Float::class.java
            Double::class.javaPrimitiveType -> Double::class.java
            else -> null
        }

    private fun inheritanceDistance(
        source: Class<*>,
        target: Class<*>,
    ): Int {
        val queue = ArrayDeque<Pair<Class<*>, Int>>()
        val visited = mutableSetOf<Class<*>>()
        queue.add(source to 0)
        while (queue.isNotEmpty()) {
            val (current, distance) = queue.removeFirst()
            if (!visited.add(current)) continue
            if (current == target) return distance
            current.superclass?.let { queue.add(it to distance + 1) }
            current.interfaces.forEach { queue.add(it to distance + 1) }
        }
        return Int.MAX_VALUE / 4
    }
}
