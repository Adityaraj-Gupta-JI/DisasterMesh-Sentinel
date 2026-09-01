package org.disastermesh.sentinel.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * DisasterMesh Sentinel — Mobile Design System.
 *
 * Matching the web Spider/Web identity. Dark-first.
 * Calm and operational: red is reserved for P0, AI output gets its own accent.
 * Every state that has a colour also has a word (see PriorityBadge).
 *
 * Rules:
 * - CriticalRed = P0 ONLY. Not generic error.
 * - AiAccent = AI output ONLY. Never human action.
 * - No decorative colour usage.
 * - Minimum touch target: Spacing.touchTarget (48dp enforced by Material).
 */

// ── Priority — semantic, not decorative ─────────────────────────────────────
val CriticalRed     = Color(0xFFE8362A)   // P0 — Critical
val UrgentOrange    = Color(0xFFD97E28)   // P1 — Urgent
val OperationalBlue = Color(0xFF2B7DD4)   // P2 — Operational / Mesh
val RoutineGrey     = Color(0xFF3D4F62)   // P3 — Routine

// ── System semantics ─────────────────────────────────────────────────────────
val VerifiedGreen   = Color(0xFF1E8F57)   // Human confirmed / online
val AiAccent        = Color(0xFF6B52C4)   // AI layer — always distinct from human
val MeshBlue        = Color(0xFF1A85CC)   // Network / mesh strands
val AmberAction     = Color(0xFFC4842A)   // Human action signal

// ── Background / Surface ─────────────────────────────────────────────────────
val DeepNavy        = Color(0xFF050A14)   // --bg deepest layer
val NavyMid         = Color(0xFF080E1B)   // --bg-mid
val NavyPanel       = Color(0xFF0B1221)   // --bg-panel
val SurfaceColor    = Color(0xFF0E1524)   // Surface glass base
val SurfaceRaised   = Color(0xFF121E30)   // Elevated surface

// ── Text ─────────────────────────────────────────────────────────────────────
val TextPrimary     = Color(0xFFE4EAF5)
val TextDim         = Color(0xFF8492A8)
val TextMicro       = Color(0xFF4E5C72)

// ── Spacing object — touch targets preserved ─────────────────────────────────
object Spacing {
    val xs: Dp = 4.dp
    val sm: Dp = 8.dp
    val md: Dp = 16.dp
    val lg: Dp = 24.dp
    val xl: Dp = 32.dp
    val xxl: Dp = 48.dp

    /** Minimum touch target for a one-handed operator under stress. */
    val touchTarget: Dp = 48.dp

    /**
     * Emergency SOS button — large enough for thumb tap under stress,
     * but proportional (not a 96dp monstrosity that crushes everything else).
     */
    val emergencyButton: Dp = 72.dp
}

// ── Color schemes ─────────────────────────────────────────────────────────────
private val DarkColors = darkColorScheme(
    primary            = MeshBlue,
    onPrimary          = Color.White,
    primaryContainer   = Color(0xFF102A45),
    onPrimaryContainer = Color(0xFF90C4E8),
    secondary          = OperationalBlue,
    onSecondary        = Color.White,
    error              = CriticalRed,
    onError            = Color.White,
    errorContainer     = Color(0xFF3D0B08),
    surface            = SurfaceColor,
    onSurface          = TextPrimary,
    surfaceVariant     = SurfaceRaised,
    onSurfaceVariant   = TextDim,
    background         = DeepNavy,
    onBackground       = TextPrimary,
    outline            = Color(0xFF2A3748),
    outlineVariant     = Color(0xFF1A2535),
)

private val LightColors = lightColorScheme(
    primary            = OperationalBlue,
    onPrimary          = Color.White,
    secondary          = MeshBlue,
    onSecondary        = Color.White,
    error              = CriticalRed,
    onError            = Color.White,
    surface            = Color(0xFFFFFFFF),
    onSurface          = Color(0xFF14181F),
    surfaceVariant     = Color(0xFFF0F3F8),
    onSurfaceVariant   = Color(0xFF5B6675),
    background         = Color(0xFFF4F6FA),
    onBackground       = Color(0xFF14181F),
    outline            = Color(0xFFCDD4DF),
    outlineVariant     = Color(0xFFE3E8F0),
)

// ── Typography — operational hierarchy ────────────────────────────────────────
private val SentinelTypography = Typography(
    // SOS and critical numbers
    displaySmall = TextStyle(
        fontSize = 28.sp,
        fontWeight = FontWeight.Bold,
        letterSpacing = (-0.02).sp,
    ),
    // Screen headings
    titleLarge = TextStyle(
        fontSize = 18.sp,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = 0.01.sp,
    ),
    // Section headings
    titleMedium = TextStyle(
        fontSize = 13.sp,
        fontWeight = FontWeight.Bold,
        letterSpacing = 0.08.sp,
    ),
    // Primary body content
    bodyLarge = TextStyle(
        fontSize = 16.sp,
        lineHeight = 24.sp,
        fontWeight = FontWeight.Normal,
    ),
    // Secondary body content
    bodyMedium = TextStyle(
        fontSize = 14.sp,
        lineHeight = 21.sp,
        fontWeight = FontWeight.Normal,
    ),
    // Metadata / micro text
    bodySmall = TextStyle(
        fontSize = 12.sp,
        lineHeight = 17.sp,
        fontWeight = FontWeight.Normal,
    ),
    // Badges and operational labels
    labelLarge = TextStyle(
        fontSize = 12.sp,
        fontWeight = FontWeight.Bold,
        letterSpacing = 0.08.sp,
    ),
    // Micro labels: timestamps, IDs, technical values
    labelSmall = TextStyle(
        fontSize = 10.sp,
        fontWeight = FontWeight.Medium,
        letterSpacing = 0.10.sp,
    ),
)

@Composable
fun SentinelTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        typography = SentinelTypography,
        content = content,
    )
}
