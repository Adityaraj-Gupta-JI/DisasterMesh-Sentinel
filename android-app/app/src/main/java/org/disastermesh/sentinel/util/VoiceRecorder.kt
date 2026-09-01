package org.disastermesh.sentinel.util

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import java.io.File

/**
 * Live microphone recording — MPEG-4/AAC, so the resulting file's MIME
 * (`audio/mp4`) is already accepted by the gateway's attachment whitelist
 * without any backend change.
 *
 * `minSdk` is 26, below the API-31 `MediaRecorder(Context)` constructor, so
 * this branches on SDK version rather than assuming the modern constructor.
 */
class VoiceRecorder(private val context: Context) {

    private var recorder: MediaRecorder? = null
    private var outputFile: File? = null

    /** Starts recording to a fresh cache file. False on any failure — caller
     * shows a "microphone unavailable" message and never crashes. */
    fun start(): Boolean {
        val file = File(context.cacheDir, "voice_${System.currentTimeMillis()}.m4a")
        @Suppress("DEPRECATION")
        val rec = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            MediaRecorder(context)
        } else {
            MediaRecorder()
        }
        return try {
            rec.apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                setOutputFile(file.absolutePath)
                prepare()
                start()
            }
            recorder = rec
            outputFile = file
            true
        } catch (_: Exception) {
            rec.release()
            file.delete()
            false
        }
    }

    /** Stops recording and returns the recorded file, or null if nothing was
     * actually captured (e.g. stop() called without a prior successful start()). */
    fun stop(): File? {
        val file = outputFile
        val rec = recorder
        recorder = null
        outputFile = null
        if (rec == null) return null
        return try {
            rec.stop()
            rec.release()
            file
        } catch (_: Exception) {
            // stop() throws if start() never actually began writing data
            // (e.g. the mic was taken by another app mid-recording).
            rec.release()
            file?.delete()
            null
        }
    }

    /** Aborts a recording in progress and discards the partial file. */
    fun cancel() {
        try {
            recorder?.stop()
        } catch (_: Exception) {
            // Nothing to salvage — discarding regardless.
        }
        recorder?.release()
        recorder = null
        outputFile?.delete()
        outputFile = null
    }
}
