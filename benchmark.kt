import kotlin.system.measureTimeMillis

fun main() {
    val nonExistentBase = "com.android.server.adb.NonExistent"

    // Baseline (looping 1..15 regardless of failure)
    val baselineTime = measureTimeMillis {
        for (j in 1..1000) { // simulate multiple calls or just amplify the effect
            for (i in 1..15) {
                runCatching { Class.forName("$nonExistentBase\$$i", false, ClassLoader.getSystemClassLoader()) }.getOrNull()
            }
        }
    }

    // Optimized (break on first failure)
    val optimizedTime = measureTimeMillis {
        for (j in 1..1000) {
            for (i in 1..15) {
                val clazz = runCatching { Class.forName("$nonExistentBase\$$i", false, ClassLoader.getSystemClassLoader()) }.getOrNull()
                if (clazz == null) break
            }
        }
    }

    println("Baseline Time (15 iterations with exceptions): $baselineTime ms")
    println("Optimized Time (break on first exception): $optimizedTime ms")
}
