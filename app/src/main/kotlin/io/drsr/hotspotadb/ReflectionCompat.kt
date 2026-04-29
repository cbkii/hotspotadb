package io.drsr.hotspotadb

import android.util.Log
import io.github.libxposed.api.XposedModule
import java.lang.reflect.Constructor
import java.lang.reflect.Field
import java.lang.reflect.Method

object ReflectionCompat {
    private const val TAG = HotspotAdbModule.TAG

    fun findFirstClass(classLoader: ClassLoader, module: XposedModule, label: String, vararg names: String): Class<*>? {
        names.forEachIndexed { index, name ->
            val clazz = tryFindClass(name, classLoader)
            if (clazz != null) {
                module.log(Log.INFO, TAG, "$label class selected [${index + 1}/${names.size}]: $name")
                return clazz
            }
            module.log(Log.DEBUG, TAG, "$label class candidate absent: $name")
        }
        module.log(Log.WARN, TAG, "$label class not found in ${names.size} candidate(s)")
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
                module.log(Log.INFO, TAG, "$label method selected ($origin): ${method.toGenericString()}")
                return method
            }
            if (!includeInherited) break
            cls = cls.superclass ?: break
        }
        module.log(Log.WARN, TAG, "$label method missing: ${clazz.name}#$name(${params.joinToString { it.simpleName }})")
        return null
    }

    fun findConstructor(clazz: Class<*>, module: XposedModule, label: String, vararg params: Class<*>): Constructor<*>? {
        val ctor = runCatching { clazz.getDeclaredConstructor(*params).also { it.isAccessible = true } }.getOrNull()
        if (ctor != null) {
            module.log(Log.INFO, TAG, "$label constructor selected: ${ctor.toGenericString()}")
            return ctor
        }
        module.log(Log.DEBUG, TAG, "$label constructor missing: ${clazz.name}(${params.joinToString { it.simpleName }})")
        return null
    }

    fun getFieldValueByName(obj: Any, name: String): Any? {
        var cls: Class<*>? = obj.javaClass
        while (cls != null && cls != Any::class.java) {
            val field = runCatching { cls.getDeclaredField(name).also { it.isAccessible = true } }.getOrNull()
            if (field != null) return field.get(obj)
            cls = cls.superclass
        }
        return null
    }

    fun getFieldValueByType(obj: Any, typeName: String): Any? {
        var cls: Class<*>? = obj.javaClass
        while (cls != null && cls != Any::class.java) {
            val field = cls.declaredFields.firstOrNull { it.type.name == typeName }?.also { it.isAccessible = true }
            if (field != null) return field.get(obj)
            cls = cls.superclass
        }
        return null
    }

    fun getFieldByNamesOrTypes(obj: Any, names: List<String>, typeNames: List<String>): Field? {
        var cls: Class<*>? = obj.javaClass
        while (cls != null && cls != Any::class.java) {
            cls.declaredFields.forEach { field ->
                if (field.name in names || field.type.name in typeNames) {
                    field.isAccessible = true
                    return field
                }
            }
            cls = cls.superclass
        }
        return null
    }

    private fun tryFindClass(name: String, classLoader: ClassLoader): Class<*>? =
        try {
            Class.forName(name, false, classLoader)
        } catch (_: ClassNotFoundException) {
            null
        }
}
