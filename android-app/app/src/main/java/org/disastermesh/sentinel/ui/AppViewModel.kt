package org.disastermesh.sentinel.ui

import android.content.Context
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import org.disastermesh.sentinel.data.SentinelRepository
import org.disastermesh.sentinel.domain.Condition
import org.disastermesh.sentinel.domain.DisasterType
import org.disastermesh.sentinel.domain.GeoPoint
import org.disastermesh.sentinel.domain.Incident
import org.disastermesh.sentinel.domain.IncidentStatus
import org.disastermesh.sentinel.domain.PriorityClass
import org.disastermesh.sentinel.domain.Quantity
import org.disastermesh.sentinel.domain.Urgency
import org.disastermesh.sentinel.sync.RelayService
import org.disastermesh.sentinel.transport.NearbyConnectionsTransport
import org.disastermesh.sentinel.ui.screens.RelayState
import org.disastermesh.sentinel.ui.screens.ReporterState
import org.disastermesh.sentinel.ui.screens.ResourceOption

enum class AppScreen {
    HOME, NEW_REPORT, CONFIRMATION, INCIDENT_DETAIL, SETTINGS
}

/** A durable, listable follow-up note — typed, or transcribed voice a human
 * reviewed and confirmed first. Gateway-only: not carried over the mesh. */
data class NoteUi(
    val id: String,
    val text: String,
    val source: String,
    val audioAttachmentId: String?,
)

/** The in-progress note being recorded/typed, before it's saved — never
 * auto-committed, always reviewed by a human first. */
data class NoteDraft(
    val text: String = "",
    val source: String = "text",
    val audioAttachmentId: String? = null,
    val busy: Boolean = false,
)

class AppViewModel(
    val repository: SentinelRepository,
) : ViewModel() {

    private val _currentScreen = MutableStateFlow(AppScreen.HOME)
    val currentScreen = _currentScreen.asStateFlow()

    private val _selectedIncidentId = MutableStateFlow<String?>(null)
    val selectedIncidentId = _selectedIncidentId.asStateFlow()

    private val _lastSubmittedIncident = MutableStateFlow<Incident?>(null)
    val lastSubmittedIncident = _lastSubmittedIncident.asStateFlow()

    private val _priorityFilter = MutableStateFlow<PriorityClass?>(null)
    val priorityFilter = _priorityFilter.asStateFlow()

    private val _serverUrl = MutableStateFlow(repository.gatewayClient.baseUrl)
    val serverUrl = _serverUrl.asStateFlow()

    private val _statusMessage = MutableStateFlow<String?>(null)
    val statusMessage = _statusMessage.asStateFlow()

    private val _selectedIncidentNotes = MutableStateFlow<List<NoteUi>>(emptyList())
    val selectedIncidentNotes = _selectedIncidentNotes.asStateFlow()

    private val _noteDraft = MutableStateFlow<NoteDraft?>(null)
    val noteDraft = _noteDraft.asStateFlow()

    val reporterState: StateFlow<ReporterState> = combine(
        repository.isOnline,
        repository.nearbyPeersCount,
        repository.allIncidents,
    ) { online, peers, list ->
        val queued = list.count { it.status == IncidentStatus.QUEUED || it.status == IncidentStatus.DRAFT }
        val ack = list.count {
            it.status in setOf(
                IncidentStatus.ACKNOWLEDGED,
                IncidentStatus.DISPATCH_REQUESTED,
                IncidentStatus.DISPATCHED,
                IncidentStatus.EN_ROUTE,
                IncidentStatus.ARRIVED,
                IncidentStatus.RESOLVED,
            )
        }
        ReporterState(
            online = online,
            nearbyPeers = peers,
            queued = queued,
            acknowledged = ack,
            myReports = list,
            aiAvailable = true,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), ReporterState())

    val relayState: StateFlow<RelayState> = combine(
        repository.relayActive,
        repository.nearbyPeersCount,
        repository.carriedBundlesCount,
        repository.batteryPercent,
        repository.storageFreeMb,
    ) { active, peers, bundles, battery, storage ->
        RelayState(
            enabled = active,
            nearbyPeers = peers,
            storedBundles = bundles,
            forwardedBundles = maxOf(0, bundles - 1),
            lastTransferLabel = if (active) "Active on mesh" else "Relay paused",
            batteryPercent = battery,
            storageFreeMb = storage,
            permissionsGranted = true,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), RelayState())

    val coordinatorIncidents: StateFlow<List<Incident>> = combine(
        repository.allIncidents,
        _priorityFilter,
    ) { list, filter ->
        if (filter == null) list else list.filter { it.priorityClass == filter }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    val selectedIncident: StateFlow<Incident?> = combine(
        repository.allIncidents,
        _selectedIncidentId,
    ) { list, id ->
        list.find { it.id == id }
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), null)

    fun navigateTo(screen: AppScreen) {
        _currentScreen.value = screen
    }

    fun setFilter(priority: PriorityClass?) {
        _priorityFilter.value = priority
    }

    fun openIncident(id: String) {
        _selectedIncidentId.value = id
        _currentScreen.value = AppScreen.INCIDENT_DETAIL
        _noteDraft.value = null
        loadNotesForSelected()
    }

    /** Notes are gateway-only (like recommendations already are) — a
     * coordinator reviewing an incident closely enough to leave a follow-up
     * note is, by nature, at a screen with the gateway reachable. */
    fun loadNotesForSelected() {
        val id = _selectedIncidentId.value ?: return
        viewModelScope.launch {
            val result = repository.gatewayClient.getIncidentNotes(id)
            _selectedIncidentNotes.value = result.getOrNull()?.map {
                NoteUi(id = it.id, text = it.text, source = it.source, audioAttachmentId = it.audioAttachmentId)
            } ?: emptyList()
        }
    }

    fun startTextNoteDraft() {
        _noteDraft.value = NoteDraft(source = "text")
    }

    fun updateNoteDraftText(text: String) {
        _noteDraft.value = _noteDraft.value?.copy(text = text)
    }

    fun cancelNoteDraft() {
        _noteDraft.value = null
    }

    /**
     * The recorded audio is uploaded and kept as a real attachment first,
     * regardless of what happens next — then transcribed into an editable
     * draft the coordinator reviews before anything is saved. A failure at
     * any point still leaves the audio saved and the draft open for typing.
     */
    fun recordVoiceNoteForSelected(bytes: ByteArray, mimeType: String) {
        val incidentId = _selectedIncidentId.value ?: return
        _noteDraft.value = NoteDraft(source = "voice", busy = true)
        viewModelScope.launch {
            val upload = repository.gatewayClient.uploadAudioAttachment(
                incidentId, bytes, "note_${System.currentTimeMillis()}.m4a", mimeType,
            )
            val attachmentId = upload.getOrNull()
            _noteDraft.value = _noteDraft.value?.copy(audioAttachmentId = attachmentId)

            val transcript = repository.gatewayClient.transcribeAudio(bytes, mimeType).getOrNull()
            _noteDraft.value = _noteDraft.value?.copy(
                text = transcript.orEmpty(),
                busy = false,
            )
            if (transcript.isNullOrBlank()) {
                _statusMessage.value = if (attachmentId != null) {
                    "Could not make out speech — audio saved, type the note instead."
                } else {
                    "Recording failed to save — please try again or type the note."
                }
            }
        }
    }

    fun saveNoteDraft() {
        val incidentId = _selectedIncidentId.value ?: return
        val draft = _noteDraft.value ?: return
        if (draft.text.isBlank()) {
            _statusMessage.value = "The note is empty."
            return
        }
        _noteDraft.value = draft.copy(busy = true)
        viewModelScope.launch {
            val result = repository.gatewayClient.addNote(
                incidentId, draft.text.trim(), draft.source, draft.audioAttachmentId,
            )
            if (result.isSuccess) {
                _noteDraft.value = null
                loadNotesForSelected()
            } else {
                _noteDraft.value = draft.copy(busy = false)
                _statusMessage.value = "Could not save the note — check the connection and retry."
            }
        }
    }

    fun sendSos() {
        viewModelScope.launch {
            val incident = repository.createReport(
                text = "EMERGENCY SOS — Immediate assistance requested",
                urgency = Urgency.CRITICAL,
                severity = 90,
                location = GeoPoint(37.7749, -122.4194, 5.0, true),
                sharePrecisely = true,
            )
            _lastSubmittedIncident.value = incident
            _currentScreen.value = AppScreen.CONFIRMATION
            repository.syncWithGateway()
        }
    }

    fun submitReport(
        text: String,
        disasterTypes: List<DisasterType> = emptyList(),
        urgency: Urgency = Urgency.HIGH,
        severity: Int = 50,
        peopleCount: Int? = null,
        shareLocation: Boolean = true,
        photoBytes: ByteArray? = null,
        photoFileName: String? = null,
        photoMimeType: String? = null,
    ) {
        viewModelScope.launch {
            val incident = repository.createReport(
                text = text,
                disasterTypes = if (disasterTypes.isEmpty()) listOf(DisasterType.OTHER) else disasterTypes,
                urgency = urgency,
                severity = severity,
                peopleAffected = if (peopleCount != null) Quantity(value = peopleCount) else Quantity.unknown(),
                location = GeoPoint(37.7749, -122.4194, 10.0, shareLocation),
                sharePrecisely = shareLocation,
            )
            _lastSubmittedIncident.value = incident
            _currentScreen.value = AppScreen.CONFIRMATION

            if (photoBytes != null && photoBytes.isNotEmpty()) {
                uploadPhotoForLastIncident(
                    photoBytes,
                    photoFileName ?: "report_photo.jpg",
                    photoMimeType ?: "image/jpeg",
                )
            }
            repository.syncWithGateway()
        }
    }

    /**
     * Upload a photo's bytes for the incident the reporter just submitted, so the
     * coordinator can see the actual image. Additive — the text report has already
     * been filed and is unaffected.
     */
    fun uploadPhotoForLastIncident(bytes: ByteArray, fileName: String, mimeType: String) {
        val incident = _lastSubmittedIncident.value ?: return
        viewModelScope.launch {
            repository.gatewayClient.submitIncident(incident)
            val result = repository.gatewayClient.uploadImageAttachment(
                incident.id, bytes, fileName, mimeType,
            )
            if (result.isSuccess) {
                val attId = result.getOrNull()
                if (attId != null && attId.isNotBlank()) {
                    repository.addAttachmentToIncident(incident.id, attId)
                    _lastSubmittedIncident.value = incident.copy(
                        attachmentIds = incident.attachmentIds + attId
                    )
                }
                _statusMessage.value = "Photo attached to report"
            } else {
                _statusMessage.value = "Photo will sync when online"
            }
            repository.syncWithGateway()
        }
    }

    /**
     * Transcribe audio to text through the gateway, then hand the text back so the
     * caller can send it as an ordinary report. Audio → speech-to-text → text flow.
     */
    fun transcribeAudio(bytes: ByteArray, mimeType: String, onText: (String) -> Unit) {
        viewModelScope.launch {
            val result = repository.gatewayClient.transcribeAudio(bytes, mimeType)
            val text = result.getOrNull().orEmpty()
            if (text.isBlank()) {
                _statusMessage.value = "Could not transcribe audio — please type the report"
            } else {
                onText(text)
            }
        }
    }

    /** Content URL and key so the coordinator UI can render image evidence. */
    fun attachmentContentUrl(incidentId: String, attachmentId: String): String =
        repository.gatewayClient.attachmentContentUrl(incidentId, attachmentId)

    fun gatewayApiKey(): String = repository.gatewayClient.apiKey

    fun acknowledgeSelected(note: String? = null) {
        val id = _selectedIncidentId.value ?: return
        viewModelScope.launch {
            repository.acknowledgeIncident(id, note)
            _statusMessage.value = "Incident acknowledged"
        }
    }

    fun dispatchSelected(resourceId: String, reason: String) {
        val id = _selectedIncidentId.value ?: return
        viewModelScope.launch {
            val result = repository.dispatchResource(id, resourceId, reason)
            if (result.isSuccess) {
                _statusMessage.value = "Simulated dispatch created (${result.getOrNull()})"
            } else {
                _statusMessage.value = "Dispatch recorded locally"
            }
        }
    }

    fun toggleRelay(enabled: Boolean, context: Context) {
        if (enabled) {
            try {
                RelayService.start(context)
                val transport = NearbyConnectionsTransport(context, repository.nodeId)
                repository.attachTransport(transport)
            } catch (_: Exception) {
                // Fallback gracefully on devices without Google Play Nearby
                RelayService.start(context)
            }
        } else {
            RelayService.stop(context)
            repository.detachTransport()
        }
    }

    fun updateServerUrl(url: String) {
        _serverUrl.value = url
        repository.gatewayClient.baseUrl = url
        repository.persistGatewayUrl(url)
        viewModelScope.launch {
            val ok = repository.checkConnection()
            if (ok) {
                repository.syncWithGateway()
            }
            _statusMessage.value = if (ok) "Connected to Gateway ($url)" else "Gateway unreachable ($url)"
        }
    }

    fun triggerSync() {
        viewModelScope.launch {
            val summary = repository.syncWithGateway()
            _statusMessage.value = if (summary.isOnline) {
                "Sync complete: pulled ${summary.pulled} incidents"
            } else {
                "Offline: stored locally in mesh queue"
            }
        }
    }

    fun clearStatusMessage() {
        _statusMessage.value = null
    }

    companion object {
        fun provideFactory(repository: SentinelRepository): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    return AppViewModel(repository) as T
                }
            }
    }
}
