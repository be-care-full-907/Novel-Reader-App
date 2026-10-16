package com.example.infinitereader

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat

class TTSPlaybackService : Service() {

    companion object {
        private const val TAG = "TTSPlaybackService"
        const val CHANNEL_ID = "infinite_reader_tts_channel"
        const val NOTIFICATION_ID = 2001

        const val ACTION_START = "com.example.infinitereader.action.START"
        const val ACTION_UPDATE = "com.example.infinitereader.action.UPDATE"
        const val ACTION_STOP = "com.example.infinitereader.action.STOP"
        const val ACTION_PLAY_PAUSE = "com.example.infinitereader.action.PLAY_PAUSE"
        const val ACTION_NEXT_CH = "com.example.infinitereader.action.NEXT_CH"
        const val ACTION_PREV_CH = "com.example.infinitereader.action.PREV_CH"

        const val EXTRA_TITLE = "extra_title"
        const val EXTRA_SUBTITLE = "extra_subtitle"
        const val EXTRA_IS_PLAYING = "extra_is_playing"

        var isServiceRunning = false
            private set

        fun start(context: Context, title: String, subtitle: String) {
            val intent = Intent(context, TTSPlaybackService::class.java).apply {
                action = ACTION_START
                putExtra(EXTRA_TITLE, title)
                putExtra(EXTRA_SUBTITLE, subtitle)
                putExtra(EXTRA_IS_PLAYING, true)
            }
            try {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    context.startForegroundService(intent)
                } else {
                    context.startService(intent)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to startForegroundService: ${e.message}")
            }
        }

        fun update(context: Context, title: String, subtitle: String, isPlaying: Boolean) {
            if (!isServiceRunning) return
            val intent = Intent(context, TTSPlaybackService::class.java).apply {
                action = ACTION_UPDATE
                putExtra(EXTRA_TITLE, title)
                putExtra(EXTRA_SUBTITLE, subtitle)
                putExtra(EXTRA_IS_PLAYING, isPlaying)
            }
            try {
                context.startService(intent)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to update notification: ${e.message}")
            }
        }

        fun stop(context: Context) {
            if (!isServiceRunning) return
            val intent = Intent(context, TTSPlaybackService::class.java).apply {
                action = ACTION_STOP
            }
            try {
                context.startService(intent)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to stop service: ${e.message}")
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                val title = intent.getStringExtra(EXTRA_TITLE) ?: "Infinite Reader"
                val subtitle = intent.getStringExtra(EXTRA_SUBTITLE) ?: "Playing"
                val isPlaying = intent.getBooleanExtra(EXTRA_IS_PLAYING, true)
                startInForeground(title, subtitle, isPlaying)
            }
            ACTION_UPDATE -> {
                val title = intent.getStringExtra(EXTRA_TITLE) ?: "Infinite Reader"
                val subtitle = intent.getStringExtra(EXTRA_SUBTITLE) ?: "Playing"
                val isPlaying = intent.getBooleanExtra(EXTRA_IS_PLAYING, true)
                updateNotification(title, subtitle, isPlaying)
            }
            ACTION_STOP -> {
                try {
                    stopForeground(STOP_FOREGROUND_REMOVE)
                } catch (e: Exception) {
                    Log.e(TAG, "Error in stopForeground: ${e.message}")
                }
                stopSelf()
                isServiceRunning = false
            }
            ACTION_PLAY_PAUSE -> {
                TTSBridge.activeBridgeInstance?.togglePlayPause()
            }
            ACTION_NEXT_CH -> {
                TTSBridge.activeBridgeInstance?.nextChapter()
            }
            ACTION_PREV_CH -> {
                TTSBridge.activeBridgeInstance?.prevChapter()
            }
        }
        return START_NOT_STICKY
    }

    private fun startInForeground(title: String, subtitle: String, isPlaying: Boolean) {
        val notification = buildNotification(title, subtitle, isPlaying)
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(
                    NOTIFICATION_ID,
                    notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK
                )
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
            isServiceRunning = true
        } catch (e: Exception) {
            Log.e(TAG, "startForeground error: ${e.message}")
        }
    }

    private fun updateNotification(title: String, subtitle: String, isPlaying: Boolean) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
        manager?.notify(NOTIFICATION_ID, buildNotification(title, subtitle, isPlaying))
    }

    private fun buildNotification(title: String, subtitle: String, isPlaying: Boolean): Notification {
        val openAppIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openAppPendingIntent = PendingIntent.getActivity(
            this,
            0,
            openAppIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val playPauseIntent = Intent(this, TTSPlaybackService::class.java).apply {
            action = ACTION_PLAY_PAUSE
        }
        val playPausePending = PendingIntent.getService(
            this,
            1,
            playPauseIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val prevIntent = Intent(this, TTSPlaybackService::class.java).apply {
            action = ACTION_PREV_CH
        }
        val prevPending = PendingIntent.getService(
            this,
            2,
            prevIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val nextIntent = Intent(this, TTSPlaybackService::class.java).apply {
            action = ACTION_NEXT_CH
        }
        val nextPending = PendingIntent.getService(
            this,
            3,
            nextIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val playPauseIcon = if (isPlaying) android.R.drawable.ic_media_pause else android.R.drawable.ic_media_play
        val playPauseText = if (isPlaying) "Pause" else "Play"

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(subtitle)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentIntent(openAppPendingIntent)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOngoing(isPlaying)
            .addAction(android.R.drawable.ic_media_previous, "Prev", prevPending)
            .addAction(playPauseIcon, playPauseText, playPausePending)
            .addAction(android.R.drawable.ic_media_next, "Next", nextPending)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Infinite Reader Audio Playback",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Shows TTS background playback controls"
                setShowBadge(false)
            }
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as? NotificationManager
            manager?.createNotificationChannel(channel)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        isServiceRunning = false
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
