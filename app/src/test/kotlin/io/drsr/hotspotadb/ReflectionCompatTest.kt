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
        val value = ReflectionCompat.getFieldValueByName(Dummy(), "baseStringField")

        assertEquals("baseString", value)
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
        val value = ReflectionCompat.getFieldValueByType(Dummy(), Long::class.java.name)

        assertNull(value)
    }

    @Test
    fun `getFieldByNamesOrTypes prioritises requested name`() {
        val field =
            ReflectionCompat.getFieldByNamesOrTypes(
                Dummy(),
                listOf("baseIntField"),
                listOf("int"),
            )

        assertNotNull(field)
        assertEquals("baseIntField", field?.name)
        assertEquals(BaseDummy::class.java, field?.declaringClass)
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
}
