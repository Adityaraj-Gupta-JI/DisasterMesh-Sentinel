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
    }

    fun sendSos() {
        viewModelScope.launch {
            val incident = repository.createReport(
                text = "EMERGENCY SOS: Life threat reported. Immediate assistance needed.",
                disasterTypes = listOf(DisasterType.MEDICAL, DisasterType.TRAPPED_PERSON),
                urgency = Urgency.CRITICAL,
                severity = 95,
                peopleAffected = Quantity(value = 1, approximate = false),
                conditions = listOf(Condition(type = org.disastermesh.sentinel.domain.ConditionType.NOT_BREATHING)),
                location = GeoPoint(37.7749, -122.4194, 5.0, true),
                sharePrecisely = true,
            )
            _lastSubmittedIncident.value = incident
            _currentScreen.value = AppScreen.CONFIRMATION
        }
    }

    fun submitReport(
        text: String,
        disasterTypes: List<DisasterType> = emptyList(),
        urgency: Urgency = Urgency.HIGH,
        severity: Int = 50,
        peopleCount: Int? = null,
        shareLocation: Boolean = true,
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
        }
    }

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
        viewModelScope.launch {
            val ok = repository.checkConnection()
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
