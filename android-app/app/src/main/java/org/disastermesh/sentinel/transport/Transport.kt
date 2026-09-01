package org.disastermesh.sentinel.transport

import kotlinx.coroutines.flow.Flow

/**
 * Transport abstraction, mirroring `protocol/dms/transport/base.py`.
 *
 * No screen, view model, or sync component may import Nearby Connections directly.
 * They talk to this interface, which is why the whole sync path is testable without
 * a second phone in the room.
 */

enum class ConnectionState { DISCOVERED, REQUESTED, CONNECTED, REJECTED, DISCONNECTED, FAILED }

enum class PayloadKind { BYTES, FILE, STREAM }

data class PeerInfo(
    val endpointId: String,
    val nodeId: String,
    val displayName: String = "",
    val metadata: Map<String, String> = emptyMap(),
)

sealed interface TransportEvent {
    data class PeerDiscovered(val peer: PeerInfo) : TransportEvent
    data class PeerLost(val endpointId: String) : TransportEvent
    data class ConnectionRequested(val peer: PeerInfo, val authenticationToken: String) : TransportEvent
    data class Connected(val peer: PeerInfo) : TransportEvent
    data class Disconnected(val endpointId: String, val reason: String? = null) : TransportEvent
    data class PayloadReceived(
        val peer: PeerInfo,
        val payloadId: String,
        val kind: PayloadKind,
        val bytes: ByteArray? = null,
        val filePath: String? = null,
    ) : TransportEvent {
        override fun equals(other: Any?): Boolean = this === other
        override fun hashCode(): Int = payloadId.hashCode()
    }
    data class PayloadProgress(
        val payloadId: String, val bytesTransferred: Long, val totalBytes: Long,
    ) : TransportEvent
    data class PayloadFailed(val payloadId: String, val reason: String) : TransportEvent
    data class Error(val reason: String) : TransportEvent
}

/** Thrown for transport faults. Callers log and continue; a radio fault never crashes the app. */
class TransportException(message: String, cause: Throwable? = null) : Exception(message, cause)

interface Transport {
    val nodeId: String
    val events: Flow<TransportEvent>

    fun startAdvertising(metadata: Map<String, String> = emptyMap())
    fun stopAdvertising()
    fun startDiscovery()
    fun stopDiscovery()

    fun requestConnection(endpointId: String, timeoutMillis: Long = 30_000)
    fun acceptConnection(endpointId: String)
    fun rejectConnection(endpointId: String, reason: String = "policy")
    fun disconnect(endpointId: String)
    fun connectionState(endpointId: String): ConnectionState

    fun sendBytes(endpointId: String, data: ByteArray): String
    fun sendFile(endpointId: String, path: String, timeoutMillis: Long = 120_000): String
    fun cancelPayload(payloadId: String)

    fun close()

    companion object {
        const val MAX_FILE_BYTES = 32L * 1024 * 1024
        const val SERVICE_ID = "org.disastermesh.sentinel.v1"
    }
}
