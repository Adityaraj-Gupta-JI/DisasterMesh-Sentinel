package org.disastermesh.sentinel.util

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Environment
import android.os.StatFs

data class DeviceTelemetryInfo(
    val batteryPercent: Int,
    val isCharging: Boolean,
    val storageFreeMb: Long,
    val storageTotalMb: Long,
)

object DeviceTelemetry {

    fun getTelemetry(context: Context): DeviceTelemetryInfo {
        var batteryPercent = 100
        var isCharging = false

        try {
            val bm = context.getSystemService(Context.BATTERY_SERVICE) as? BatteryManager
            if (bm != null) {
                val capacity = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
                if (capacity in 0..100) {
                    batteryPercent = capacity
                }
            }

            val iFilter = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
            val batteryStatus: Intent? = context.registerReceiver(null, iFilter)
            if (batteryStatus != null) {
                val level = batteryStatus.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
                val scale = batteryStatus.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
                if (level >= 0 && scale > 0) {
                    batteryPercent = (level * 100 / scale.toFloat()).toInt()
                }

                val status = batteryStatus.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
                isCharging = status == BatteryManager.BATTERY_STATUS_CHARGING ||
                    status == BatteryManager.BATTERY_STATUS_FULL
            }
        } catch (_: Exception) {
            batteryPercent = 100
        }

        var storageFreeMb = 1024L
        var storageTotalMb = 4096L
        try {
            val path = context.filesDir ?: Environment.getDataDirectory()
            val stat = StatFs(path.absolutePath)
            val blockSize = stat.blockSizeLong
            val availableBlocks = stat.availableBlocksLong
            val totalBlocks = stat.blockCountLong

            storageFreeMb = (availableBlocks * blockSize) / (1024 * 1024)
            storageTotalMb = (totalBlocks * blockSize) / (1024 * 1024)
        } catch (_: Exception) {
            storageFreeMb = 1024L
        }

        return DeviceTelemetryInfo(
            batteryPercent = batteryPercent.coerceIn(0, 100),
            isCharging = isCharging,
            storageFreeMb = storageFreeMb,
            storageTotalMb = storageTotalMb,
        )
    }
}
