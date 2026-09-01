package org.disastermesh.sentinel

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.List
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import org.disastermesh.sentinel.ui.AppScreen
import org.disastermesh.sentinel.ui.AppViewModel
import org.disastermesh.sentinel.ui.screens.CoordinatorInboxScreen
import org.disastermesh.sentinel.ui.screens.IncidentDetailScreen
import org.disastermesh.sentinel.ui.screens.NewIncidentScreen
import org.disastermesh.sentinel.ui.screens.RelayScreen
import org.disastermesh.sentinel.ui.screens.ReporterHomeScreen
import org.disastermesh.sentinel.ui.screens.SubmissionConfirmationScreen
import org.disastermesh.sentinel.ui.theme.Badge
import org.disastermesh.sentinel.ui.theme.SentinelTheme
import org.disastermesh.sentinel.ui.theme.VerifiedGreen
import org.disastermesh.sentinel.ui.theme.RoutineGrey

/**
 * Single activity hosting all role experiences and full end-to-end communication logic.
 */
class MainActivity : ComponentActivity() {

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        val granted = permissions.entries.all { it.value }
        if (!granted) {
            Toast.makeText(this, "Some mesh permissions were denied; offline local mode active", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        requestMeshPermissions()

        val app = application as SentinelApplication
        val repository = app.repository

        setContent {
            SentinelTheme {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    val viewModel: AppViewModel = viewModel(
                        factory = AppViewModel.provideFactory(repository)
                    )
                    SentinelApp(
                        viewModel = viewModel,
                        onRequestPermissions = { requestMeshPermissions() },
                    )
                }
            }
        }
    }

    private fun requestMeshPermissions() {
        val needed = mutableListOf<String>()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            needed.add(Manifest.permission.BLUETOOTH_SCAN)
            needed.add(Manifest.permission.BLUETOOTH_ADVERTISE)
            needed.add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            needed.add(Manifest.permission.POST_NOTIFICATIONS)
            needed.add(Manifest.permission.NEARBY_WIFI_DEVICES)
        }
        needed.add(Manifest.permission.ACCESS_FINE_LOCATION)
        needed.add(Manifest.permission.ACCESS_COARSE_LOCATION)

        val ungranted = needed.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (ungranted.isNotEmpty()) {
            permissionLauncher.launch(ungranted.toTypedArray())
        }
    }
}

private enum class Tab(val label: String) { REPORT("Report"), RELAY("Relay"), INBOX("Inbox") }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SentinelApp(
    viewModel: AppViewModel,
    onRequestPermissions: () -> Unit,
) {
    val context = LocalContext.current
    var currentTab by remember { mutableStateOf(Tab.REPORT) }
    var showSettingsDialog by remember { mutableStateOf(false) }

    val currentScreen by viewModel.currentScreen.collectAsState()
    val reporterState by viewModel.reporterState.collectAsState()
    val relayState by viewModel.relayState.collectAsState()
    val coordinatorIncidents by viewModel.coordinatorIncidents.collectAsState()
    val priorityFilter by viewModel.priorityFilter.collectAsState()
    val lastIncident by viewModel.lastSubmittedIncident.collectAsState()
    val selectedIncident by viewModel.selectedIncident.collectAsState()
    val serverUrl by viewModel.serverUrl.collectAsState()
    val statusMessage by viewModel.statusMessage.collectAsState()

    LaunchedEffect(statusMessage) {
        statusMessage?.let {
            Toast.makeText(context, it, Toast.LENGTH_SHORT).show()
            viewModel.clearStatusMessage()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("DisasterMesh Sentinel", style = MaterialTheme.typography.titleMedium)
                        Text("Node: ${viewModel.repository.nodeId}", style = MaterialTheme.typography.labelSmall)
                    }
                },
                actions = {
                    val isOnline = reporterState.online
                    Badge(
                        text = if (isOnline) "Online" else "Mesh Only",
                        color = if (isOnline) VerifiedGreen else RoutineGrey,
                        filled = true,
                        modifier = Modifier
                            .clickable { showSettingsDialog = true }
                            .padding(end = 4.dp),
                    )
                    IconButton(onClick = { viewModel.triggerSync() }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Sync now")
                    }
                    IconButton(onClick = { showSettingsDialog = true }) {
                        Icon(Icons.Filled.Settings, contentDescription = "Server Settings")
                    }
                },
            )
        },
        bottomBar = {
            if (currentScreen == AppScreen.HOME) {
                NavigationBar {
                    Tab.entries.forEach { entry ->
                        NavigationBarItem(
                            selected = currentTab == entry,
                            onClick = { currentTab = entry },
                            icon = {
                                Icon(
                                    when (entry) {
                                        Tab.REPORT -> Icons.Filled.Home
                                        Tab.RELAY -> Icons.Filled.Share
                                        Tab.INBOX -> Icons.Filled.List
                                    },
                                    contentDescription = entry.label,
                                )
                            },
                            label = { Text(entry.label) },
                        )
                    }
                }
            }
        },
    ) { padding ->
        val content = Modifier
            .fillMaxSize()
            .padding(padding)

        when (currentScreen) {
            AppScreen.HOME -> {
                when (currentTab) {
                    Tab.REPORT -> ReporterHomeScreen(
                        state = reporterState,
                        onStartReport = { viewModel.navigateTo(AppScreen.NEW_REPORT) },
                        onStartVoiceReport = {
                            viewModel.submitReport(
                                text = "Voice memo incident report (auto-transcribed)",
                                urgency = org.disastermesh.sentinel.domain.Urgency.HIGH,
                                severity = 60,
                            )
                        },
                        onOpenReport = { id -> viewModel.openIncident(id) },
                        modifier = content,
                    )
                    Tab.RELAY -> RelayScreen(
                        state = relayState,
                        onToggleRelay = { enabled -> viewModel.toggleRelay(enabled, context) },
                        onRequestPermissions = onRequestPermissions,
                        modifier = content,
                    )
                    Tab.INBOX -> CoordinatorInboxScreen(
                        incidents = coordinatorIncidents,
                        filter = priorityFilter,
                        pendingSync = reporterState.queued,
                        onFilter = { viewModel.setFilter(it) },
                        onOpen = { id -> viewModel.openIncident(id) },
                        modifier = content,
                    )
                }
            }
            AppScreen.NEW_REPORT -> {
                NewIncidentScreen(
                    aiAvailable = reporterState.aiAvailable,
                    suggestion = Pair("Recommended Priority", listOf("P1 Urgent based on high impact", "Text will synchronize before attachments")),
                    submitting = false,
                    onSubmit = { text, disasterTypes, urgency, peopleCount, shareLocation ->
                        viewModel.submitReport(text, disasterTypes, urgency, 70, peopleCount, shareLocation)
                    },
                    onCancel = { viewModel.navigateTo(AppScreen.HOME) },
                    modifier = content,
                )
            }
            AppScreen.CONFIRMATION -> {
                if (lastIncident != null) {
                    SubmissionConfirmationScreen(
                        incident = lastIncident!!,
                        onAddPhoto = {
                            Toast.makeText(context, "Photo metadata attached to bundle", Toast.LENGTH_SHORT).show()
                            viewModel.navigateTo(AppScreen.HOME)
                        },
                        onDone = { viewModel.navigateTo(AppScreen.HOME) },
                        modifier = content,
                    )
                } else {
                    viewModel.navigateTo(AppScreen.HOME)
                }
            }
            AppScreen.INCIDENT_DETAIL -> {
                if (selectedIncident != null) {
                    IncidentDetailScreen(
                        incident = selectedIncident!!,
                        recommendations = emptyList(),
                        onAcknowledge = { viewModel.acknowledgeSelected() },
                        onDispatch = { resourceId, reason -> viewModel.dispatchSelected(resourceId, reason) },
                        onBack = { viewModel.navigateTo(AppScreen.HOME) },
                        modifier = content,
                    )
                } else {
                    viewModel.navigateTo(AppScreen.HOME)
                }
            }
            AppScreen.SETTINGS -> {
                viewModel.navigateTo(AppScreen.HOME)
            }
        }
    }

    if (showSettingsDialog) {
        var inputUrl by remember { mutableStateOf(serverUrl) }
        AlertDialog(
            onDismissRequest = { showSettingsDialog = false },
            title = { Text("Gateway Connection & Port Forwarding") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(
                        "Connect to the Central Gateway via Local Wi-Fi, USB ADB Reverse, or Public Cloud Tunnel.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    OutlinedTextField(
                        value = inputUrl,
                        onValueChange = { inputUrl = it },
                        label = { Text("Server URL") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Text("Quick Connection Presets:", style = MaterialTheme.typography.labelSmall)
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        androidx.compose.material3.AssistChip(
                            onClick = { inputUrl = "http://127.0.0.1:8000" },
                            label = { Text("USB / ADB") },
                        )
                        androidx.compose.material3.AssistChip(
                            onClick = { inputUrl = "http://10.0.2.2:8000" },
                            label = { Text("Emulator") },
                        )
                    }
                    Text(
                        "Tip: If Wi-Fi router blocks device-to-device traffic, run:\n'adb reverse tcp:8000 tcp:8000' (over USB) or use a Cloudflare/ngrok tunnel.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            },
            confirmButton = {
                Button(onClick = {
                    viewModel.updateServerUrl(inputUrl)
                    showSettingsDialog = false
                }) {
                    Text("Save & Connect")
                }
            },
            dismissButton = {
                TextButton(onClick = { showSettingsDialog = false }) {
                    Text("Cancel")
                }
            },
        )
    }
}
