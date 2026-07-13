package io.drsr.hotspotadb

import io.github.libxposed.api.XposedModule
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test
import org.mockito.kotlin.mock

class ReflectionCompatTest {
    private lateinit var mockModule: XposedModule
    private lateinit var classLoader: ClassLoader

    @Before
    fun setUp() {
        mockModule = mock()
        classLoader = this::class.java.classLoader!!
    }

    open class BaseDummy {
        protected open fun baseMethod(): String = "base"
        val baseStringField: String = "baseString"
        private val baseIntField: Int = 10
        val baseDoubleField: Double = 3.14
    }

    class Dummy() : BaseDummy() {
        private val intField: Int = 42
        val stringField: String = "hello"

        private constructor(value: Int) : this() {
            require(value >= 0)
        }

        fun publicMethod(): String = "public"
        private fun privateMethod(value: Int): Int = value * 2
    }

    class OverloadDummy {
        fun select(value: Int): String = "int:$value"
        fun select(value: Number): String = "number:$value"
        fun reference(value: Number): String = "number:$value"
        fun reference(value: Any): String = "any:$value"
        fun primitiveOnly(value: Int): Int = value
        fun nullable(value: String?): String? = value
        fun byteValue(value: Byte): Byte = value
        fun shortValue(value: Short): Short = value
        fun charValue(value: Char): Char = value
    }

    @Test
    fun `findFirstClass finds first existing class`() {
        val clazz =
            ReflectionCompat.findFirstClass(
                classLoader,
                mockModule,
                "Dummy",
                "non.existent.Class",
                Dummy::class.java.name,
            )
        assertEquals(Dummy::class.java, clazz)
    }

    @Test
    fun `findFirstClass returns null when all candidates are absent`() {
        val clazz =
            ReflectionCompat.findFirstClass(
                classLoader,
                mockModule,
                "Dummy",
                "non.existent.Class1",
                "non.existent.Class2",
            )
        assertNull(clazz)
    }

    @Test
    fun `findMethod finds declared public method`() {
        val method =
            ReflectionCompat.findMethod(
                Dummy::class.java,
                mockModule,
                "publicMethod",
                "publicMethod",
                false,
            )
        assertNotNull(method)
        assertEquals("publicMethod", method?.name)
    }

    @Test
    fun `findMethod finds declared private method`() {
        val method =
            ReflectionCompat.findMethod(
                Dummy::class.java,
                mockModule,
                "privateMethod",
                "privateMethod",
                false,
                Int::class.java,
            )
        assertNotNull(method)
        assertEquals("privateMethod", method?.name)
    }

    @Test
    fun `findMethod finds inherited protected method when requested`() {
        val method =
            ReflectionCompat.findMethod(
                Dummy::class.java,
                mockModule,
                "baseMethod",
                "baseMethod",
                true,
            )
        assertNotNull(method)
        assertEquals("baseMethod", method?.name)
        assertEquals(BaseDummy::class.java, method?.declaringClass)
    }

    @Test
    fun `findMethod excludes inherited method when not requested`() {
        val method =
            ReflectionCompat.findMethod(
                Dummy::class.java,
                mockModule,
                "baseMethod",
                "baseMethod",
                false,
            )
        assertNull(method)
    }

    @Test
    fun `findConstructor finds no-arg constructor`() {
        val constructor =
            ReflectionCompat.findConstructor(
                Dummy::class.java,
                mockModule,
                "DummyCtor",
            )
        assertNotNull(constructor)
        assertEquals(0, constructor?.parameterCount)
    }

    @Test
    fun `findConstructor finds private constructor with arguments`() {
        val constructor =
            ReflectionCompat.findConstructor(
                Dummy::class.java,
                mockModule,
                "DummyCtor",
                Int::class.java,
            )
        assertNotNull(constructor)
        assertEquals(1, constructor?.parameterCount)
    }

    @Test
    fun `getFieldValueByName reads field from current class`() {
        assertEquals(42, ReflectionCompat.getFieldValueByName(Dummy(), "intField"))
    }

    @Test
    fun `getFieldValueByName reads field from base class`() {
        assertEquals("baseString", ReflectionCompat.getFieldValueByName(Dummy(), "baseStringField"))
    }

    @Test
    fun `getFieldValueByName returns null for absent field`() {
        assertNull(ReflectionCompat.getFieldValueByName(Dummy(), "missingField"))
    }

    @Test
    fun `getFieldValueByType reads first matching field from current class`() {
        assertEquals(42, ReflectionCompat.getFieldValueByType(Dummy(), "int"))
    }

    @Test
    fun `getFieldValueByType walks into base class for unique type`() {
        val value = ReflectionCompat.getFieldValueByType(Dummy(), "double")
        assertEquals(3.14, value as Double, 0.0)
    }

    @Test
    fun `getFieldValueByType returns null for absent type`() {
        assertNull(ReflectionCompat.getFieldValueByType(Dummy(), Long::class.java.name))
    }

    @Test
    fun `getFieldByNamesOrTypes prioritises requested name at current class level`() {
        val field =
            ReflectionCompat.getFieldByNamesOrTypes(
                Dummy(),
                listOf("stringField"),
                listOf("int"),
            )
        assertNotNull(field)
        assertEquals("stringField", field?.name)
        assertEquals(Dummy::class.java, field?.declaringClass)
    }

    @Test
    fun `getFieldByNamesOrTypes falls back to requested type`() {
        val field =
            ReflectionCompat.getFieldByNamesOrTypes(
                Dummy(),
                listOf("missingField"),
                listOf("double"),
            )
        assertNotNull(field)
        assertEquals("baseDoubleField", field?.name)
        assertEquals(BaseDummy::class.java, field?.declaringClass)
    }

    @Test
    fun `getFieldByNamesOrTypes returns null when no candidate matches`() {
        val field =
            ReflectionCompat.getFieldByNamesOrTypes(
                Dummy(),
                listOf("missingField"),
                listOf(Long::class.java.name),
            )
        assertNull(field)
    }

    @Test
    fun `compatible method prefers boxed primitive exact match`() {
        val method =
            ReflectionCompat.findCompatibleMethod(
                OverloadDummy::class.java,
                "select",
                arrayOf(42),
            )
        assertNotNull(method)
        assertEquals(Int::class.javaPrimitiveType, method?.parameterTypes?.single())
    }

    @Test
    fun `compatible method rejects null for primitive parameter`() {
        val method =
            ReflectionCompat.findCompatibleMethod(
                OverloadDummy::class.java,
                "primitiveOnly",
                arrayOf(null),
            )
        assertNull(method)
    }

    @Test
    fun `compatible method accepts null for reference parameter`() {
        val method =
            ReflectionCompat.findCompatibleMethod(
                OverloadDummy::class.java,
                "nullable",
                arrayOf(null),
            )
        assertNotNull(method)
        assertEquals(String::class.java, method?.parameterTypes?.single())
    }

    @Test
    fun `compatible method prefers nearest assignable reference type`() {
        val method =
            ReflectionCompat.findCompatibleMethod(
                OverloadDummy::class.java,
                "reference",
                arrayOf(42),
            )
        assertNotNull(method)
        assertEquals(Number::class.java, method?.parameterTypes?.single())
    }

    @Test
    fun `compatible method supports byte short and char primitives`() {
        val cases =
            listOf(
                Triple("byteValue", 1.toByte(), Byte::class.javaPrimitiveType),
                Triple("shortValue", 1.toShort(), Short::class.javaPrimitiveType),
                Triple("charValue", 'x', Char::class.javaPrimitiveType),
            )
        cases.forEach { (name, value, expectedType) ->
            val method =
                ReflectionCompat.findCompatibleMethod(
                    OverloadDummy::class.java,
                    name,
                    arrayOf(value),
                )
            assertNotNull(name, method)
            assertEquals(name, expectedType, method?.parameterTypes?.single())
        }
    }
}
