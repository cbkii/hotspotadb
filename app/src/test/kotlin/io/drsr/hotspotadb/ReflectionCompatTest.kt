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

    // Dummy classes for testing
    open class BaseDummy {
        protected open fun baseMethod(): String = "base"

        val baseStringField: String = "baseString"
        private val baseIntField: Int = 10
    }

    class Dummy() : BaseDummy() {
        private val intField: Int = 42
        val stringField: String = "hello"

        private constructor(value: Int) : this() {
            // Do nothing
        }

        fun publicMethod(): String = "public"

        private fun privateMethod(value: Int): Int = value * 2
    }

    @Test
    fun `findFirstClass finds existing class`() {
        val clazz =
            ReflectionCompat.findFirstClass(
                classLoader,
                mockModule,
                "Dummy",
                "non.existent.Class",
                Dummy::class.java.name,
            )
        assertNotNull(clazz)
        assertEquals(Dummy::class.java, clazz)
    }

    @Test
    fun `findFirstClass returns null when class not found`() {
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
    fun `findMethod finds inherited method when includeInherited is true`() {
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
    }

    @Test
    fun `findMethod does not find inherited method when includeInherited is false`() {
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
        val ctor =
            ReflectionCompat.findConstructor(
                Dummy::class.java,
                mockModule,
                "DummyCtor",
            )
        assertNotNull(ctor)
        assertEquals(0, ctor?.parameterCount)
    }

    @Test
    fun `findConstructor finds private constructor with args`() {
        val ctor =
            ReflectionCompat.findConstructor(
                Dummy::class.java,
                mockModule,
                "DummyCtor",
                Int::class.java,
            )
        assertNotNull(ctor)
        assertEquals(1, ctor?.parameterCount)
    }

    @Test
    fun `getFieldValueByName gets field value from current class`() {
        val dummy = Dummy()
        val value = ReflectionCompat.getFieldValueByName(dummy, "intField")
        assertEquals(42, value)
    }

    @Test
    fun `getFieldValueByName gets field value from base class`() {
        val dummy = Dummy()
        val value = ReflectionCompat.getFieldValueByName(dummy, "baseStringField")
        assertEquals("baseString", value)
    }

    @Test
    fun `getFieldValueByType gets field value from current class`() {
        val dummy = Dummy()
        val value = ReflectionCompat.getFieldValueByType(dummy, "int")
        assertEquals(42, value)
    }

    @Test
    fun `getFieldValueByType gets field value from base class`() {
        val dummy = Dummy()
        // java.lang.String for Kotlin String mapped field
        val value = ReflectionCompat.getFieldValueByType(dummy, String::class.java.name)
        assertEquals("hello", value)
    }

    @Test
    fun `getFieldByNamesOrTypes gets field by name`() {
        val dummy = Dummy()
        val field =
            ReflectionCompat.getFieldByNamesOrTypes(
                dummy,
                listOf("baseIntField"),
                emptyList(),
            )
        assertNotNull(field)
        assertEquals("baseIntField", field?.name)
    }

    @Test
    fun `getFieldByNamesOrTypes gets field by type`() {
        val dummy = Dummy()
        val field =
            ReflectionCompat.getFieldByNamesOrTypes(
                dummy,
                emptyList(),
                listOf("int"),
            )
        assertNotNull(field)
        assertEquals("int", field?.type?.name)
    }
}
