package org.disastermesh.sentinel.sync

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder

/**
 * Foreground relay service.
 *
 * Relaying runs in the foreground on purpose: a device that carries other people's
 * emergency data must never do so invisibly. The notification is the honest indicator
 * that radios are active, and it exposes a pause action.
 */
class RelayService : Service() {

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIFICATION_ID, buildNotification(carried = 0, forwarded = 0))
        return START_STICKY
    }

    private fun buildNotification(carried: Int, forwarded: Int): Notification {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            manager.createNotificationChannel(
                NotificationChannel(
                    CHANNEL_ID,
                    "Relay mode",
                    NotificationManager.IMPORTANCE_LOW,
                ).apply {
                    description = "Shown while this phone is carrying emergency reports for others."
                }
            )
        }
        return Notification.Builder(this, CHANNEL_ID)
            .setContentTitle("Relaying emergency reports")
            .setContentText("Carrying $carried · passed on $forwarded")
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val CHANNEL_ID = "dms_relay"
        private const val NOTIFICATION_ID = 1001

        fun start(context: Context) {
            context.startForegroundService(Intent(context, RelayService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, RelayService::class.java))
        }
    }
}
