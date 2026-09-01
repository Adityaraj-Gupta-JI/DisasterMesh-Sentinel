package org.disastermesh.sentinel.transport

import android.content.Context
import android.util.Log
import com.google.android.gms.nearby.Nearby
import com.google.android.gms.nearby.connection.AdvertisingOptions
import com.google.android.gms.nearby.connection.ConnectionInfo
import com.google.android.gms.nearby.connection.ConnectionLifecycleCallback
import com.google.android.gms.nearby.connection.ConnectionResolution
import com.google.android.gms.nearby.connection.ConnectionsClient
import com.google.android.gms.nearby.connection.ConnectionsStatusCodes
import com.google.android.gms.nearby.connection.DiscoveredEndpointInfo
import com.google.android.gms.nearby.connection.DiscoveryOptions
import com.google.android.gms.nearby.connection.EndpointDiscoveryCallback
import com.google.android.gms.nearby.connection.Payload
import com.google.android.gms.nearby.connection.PayloadCallback
import com.google.android.gms.nearby.connection.PayloadTransferUpdate
import com.google.android.gms.nearby.connection.Strategy
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import java.io.File
import java.util.concurrent.ConcurrentHashMap

/**
 * Nearby Connections adapter.
 *
 * ⚠ NOT YET VERIFIED ON HARDWARE. This compiles against the Nearby API surface and is
 * covered by fake-callback tests, but no two-device radio test has been run — see
 * docs/DEVELOPMENT_STATUS.md. Do not claim radio validation until that happens.
 *
 * P2P_CLUSTER is used so one device can hold several simultaneous links, which is what
 * store-and-forward relaying needs. Byte payloads carry control frames and bundles;
 * file payloads carry attachments.
 */
class NearbyConnectionsTransport(
    context: Context,
    override val nodeId: String,
    private val client: ConnectionsClient = Nearby.getConnectionsClient(context),
    private val onAuthentication: (PeerInfo, String) -> Boolean = { _, _ -> true },
) : Transport {

    private val tag = "DMS/Nearby"
    private val _events = MutableSharedFlow<TransportEvent>(
        replay = 0, extraBufferCapacity = 128, onBufferOverflow = BufferOverflow.DROP_OLDEST,
    )
    override val events: Flow<TransportEvent> = _events.asSharedFlow()

    private val states = ConcurrentHashMap<String, ConnectionState>()
    private val peers = ConcurrentHashMap<String, PeerInfo>()
    private val incomingFiles = ConcurrentHashMap<Long, Payload>()

    private fun emit(event: TransportEvent) {
        _events.tryEmit(event)
    }

    // ------------------------------------------------------------- advertising

    override fun startAdvertising(metadata: Map<String, String>) {
        val advertisedName = buildString {
            append(nodeId)
            metadata["role"]?.let { append("|").append(it) }
        }
        client.startAdvertising(
            advertisedName,
            Transport.SERVICE_ID,
            connectionLifecycle,
            AdvertisingOptions.Builder().setStrategy(Strategy.P2P_CLUSTER).build(),
        ).addOnFailureListener { error ->
            Log.w(tag, "advertising failed", error)
            emit(TransportEvent.Error("advertising_failed: ${error.message}"))
        }
    }

    override fun stopAdvertising() = client.stopAdvertising()

    override fun startDiscovery() {
        client.startDiscovery(
            Transport.SERVICE_ID,
            endpointDiscovery,
            DiscoveryOptions.Builder().setStrategy(Strategy.P2P_CLUSTER).build(),
        ).addOnFailureListener { error ->
            Log.w(tag, "discovery failed", error)
            emit(TransportEvent.Error("discovery_failed: ${error.message}"))
        }
    }

    override fun stopDiscovery() = client.stopDiscovery()

    // ------------------------------------------------------------- connections

    override fun requestConnection(endpointId: String, timeoutMillis: Long) {
        // Discovery re-announces endpoints periodically even while already linked;
        // re-requesting on top of a live or in-flight connection is what causes the
        // Nearby stack to flap a good link, so this is a no-op once past DISCOVERED.
        when (states[endpointId]) {
            ConnectionState.CONNECTED, ConnectionState.REQUESTED -> return
            else -> {}
        }
        states[endpointId] = ConnectionState.REQUESTED
        client.requestConnection(nodeId, endpointId, connectionLifecycle)
            .addOnFailureListener { error ->
                states[endpointId] = ConnectionState.FAILED
                emit(TransportEvent.Error("connect_failed: ${error.message}"))
            }
    }

    override fun acceptConnection(endpointId: String) {
        client.acceptConnection(endpointId, payloadCallback)
    }

    override fun rejectConnection(endpointId: String, reason: String) {
        states[endpointId] = ConnectionState.REJECTED
        client.rejectConnection(endpointId)
    }

    override fun disconnect(endpointId: String) {
        client.disconnectFromEndpoint(endpointId)
        states[endpointId] = ConnectionState.DISCONNECTED
    }

    override fun connectionState(endpointId: String): ConnectionState =
        states[endpointId] ?: ConnectionState.DISCONNECTED

    // ---------------------------------------------------------------- payloads

    override fun sendBytes(endpointId: String, data: ByteArray): String {
        check(connectionState(endpointId) == ConnectionState.CONNECTED) {
            "not connected to $endpointId"
        }
        val payload = Payload.fromBytes(data)
        client.sendPayload(endpointId, payload)
        return payload.id.toString()
    }

    override fun sendFile(endpointId: String, path: String, timeoutMillis: Long): String {
        check(connectionState(endpointId) == ConnectionState.CONNECTED) {
            "not connected to $endpointId"
        }
        val file = File(path)
        if (file.length() > Transport.MAX_FILE_BYTES) {
            throw TransportException("file ${file.length()}B exceeds transport limit")
        }
        val payload = Payload.fromFile(file)
        client.sendPayload(endpointId, payload)
        return payload.id.toString()
    }

    override fun cancelPayload(payloadId: String) {
        payloadId.toLongOrNull()?.let { client.cancelPayload(it) }
    }

    override fun close() {
        client.stopAllEndpoints()
        states.clear()
        peers.clear()
        incomingFiles.clear()
    }

    // --------------------------------------------------------------- callbacks

    private val endpointDiscovery = object : EndpointDiscoveryCallback() {
        override fun onEndpointFound(endpointId: String, info: DiscoveredEndpointInfo) {
            val parts = info.endpointName.split("|")
            val peer = PeerInfo(
                endpointId = endpointId,
                nodeId = parts.firstOrNull().orEmpty(),
                displayName = info.endpointName,
                metadata = if (parts.size > 1) mapOf("role" to parts[1]) else emptyMap(),
            )
            peers[endpointId] = peer
            states[endpointId] = ConnectionState.DISCOVERED
            emit(TransportEvent.PeerDiscovered(peer))
        }

        override fun onEndpointLost(endpointId: String) {
            // This fires when the BLE advertisement is no longer heard, which is
            // routine once two devices are actively connected (radios busy moving
            // data instead of beaconing). It is not a disconnect — onDisconnected
            // is — so an already-CONNECTED link must not be downgraded here.
            if (states[endpointId] != ConnectionState.CONNECTED) {
                states[endpointId] = ConnectionState.DISCONNECTED
            }
            emit(TransportEvent.PeerLost(endpointId))
        }
    }

    private val connectionLifecycle = object : ConnectionLifecycleCallback() {
        override fun onConnectionInitiated(endpointId: String, info: ConnectionInfo) {
            val peer = peers[endpointId] ?: PeerInfo(endpointId, info.endpointName)
            peers[endpointId] = peer
            emit(TransportEvent.ConnectionRequested(peer, info.authenticationDigits))
            // Acceptance is a policy decision, not an automatic yes.
            if (onAuthentication(peer, info.authenticationDigits)) {
                acceptConnection(endpointId)
            } else {
                rejectConnection(endpointId, "authentication_declined")
            }
        }

        override fun onConnectionResult(endpointId: String, resolution: ConnectionResolution) {
            when (resolution.status.statusCode) {
                ConnectionsStatusCodes.STATUS_OK -> {
                    states[endpointId] = ConnectionState.CONNECTED
                    emit(TransportEvent.Connected(peers[endpointId] ?: PeerInfo(endpointId, endpointId)))
                }
                ConnectionsStatusCodes.STATUS_CONNECTION_REJECTED -> {
                    states[endpointId] = ConnectionState.REJECTED
                    emit(TransportEvent.Disconnected(endpointId, "rejected"))
                }
                else -> {
                    states[endpointId] = ConnectionState.FAILED
                    emit(TransportEvent.Disconnected(endpointId, "error"))
                }
            }
        }

        override fun onDisconnected(endpointId: String) {
            states[endpointId] = ConnectionState.DISCONNECTED
            emit(TransportEvent.Disconnected(endpointId))
        }
    }

    private val payloadCallback = object : PayloadCallback() {
        override fun onPayloadReceived(endpointId: String, payload: Payload) {
            val peer = peers[endpointId] ?: PeerInfo(endpointId, endpointId)
            when (payload.type) {
                Payload.Type.BYTES -> emit(
                    TransportEvent.PayloadReceived(
                        peer, payload.id.toString(), PayloadKind.BYTES, bytes = payload.asBytes(),
                    )
                )
                // A file is held until its transfer completes: nothing is opened,
                // executed, or committed before the digest is verified upstream.
                Payload.Type.FILE -> incomingFiles[payload.id] = payload
                else -> emit(TransportEvent.Error("unsupported_payload_type"))
            }
        }

        override fun onPayloadTransferUpdate(endpointId: String, update: PayloadTransferUpdate) {
            when (update.status) {
                PayloadTransferUpdate.Status.IN_PROGRESS -> emit(
                    TransportEvent.PayloadProgress(
                        update.payloadId.toString(), update.bytesTransferred, update.totalBytes,
                    )
                )
                PayloadTransferUpdate.Status.SUCCESS -> {
                    val payload = incomingFiles.remove(update.payloadId) ?: return
                    val peer = peers[endpointId] ?: PeerInfo(endpointId, endpointId)
                    val path = payload.asFile()?.asJavaFile()?.absolutePath
                    emit(
                        TransportEvent.PayloadReceived(
                            peer, update.payloadId.toString(), PayloadKind.FILE, filePath = path,
                        )
                    )
                }
                PayloadTransferUpdate.Status.FAILURE, PayloadTransferUpdate.Status.CANCELED -> {
                    incomingFiles.remove(update.payloadId)
                    emit(
                        TransportEvent.PayloadFailed(
                            update.payloadId.toString(),
                            if (update.status == PayloadTransferUpdate.Status.CANCELED)
                                "cancelled" else "transfer_failed",
                        )
                    )
                }
            }
        }
    }
}
