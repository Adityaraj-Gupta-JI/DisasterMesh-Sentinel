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
 * Design system.
 *
 * Calm and operational: red is reserved for P0, AI output gets its own accent so it is
 * never mistaken for a human decision, and every state that has a colour also has a
 * word (see PriorityBadge).
 */

val CriticalRed = Color(0xFFD32F2F)
val UrgentOrange = Color(0xFFE07000)
val OperationalBlue = Color(0xFF1E62D0)
val RoutineGrey = Color(0xFF5B6675)
val VerifiedGreen = Color(0xFF157F3B)
val AiAccent = Color(0xFF7C5CD6)

object Spacing {
    val xs: Dp = 4.dp
    val sm: Dp = 8.dp
    val md: Dp = 16.dp
    val lg: Dp = 24.dp
    val xl: Dp = 32.dp

    /** Minimum touch target for a one-handed operator under stress. */
    val touchTarget: Dp = 48.dp
    val emergencyButton: Dp = 96.dp
}

private val LightColors = lightColorScheme(
    primary = OperationalBlue,
    error = CriticalRed,
    surface = Color(0xFFFFFFFF),
    background = Color(0xFFF6F7F9),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF7BA7F0),
    error = Color(0xFFFF6B6D),
    surface = Color(0xFF171A21),
    background = Color(0xFF0F1115),
)

private val SentinelTypography = Typography(
    displaySmall = TextStyle(fontSize = 30.sp, fontWeight = FontWeight.Bold),
    titleLarge = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.SemiBold),
    bodyLarge = TextStyle(fontSize = 17.sp, lineHeight = 25.sp),
    bodyMedium = TextStyle(fontSize = 15.sp, lineHeight = 22.sp),
    labelSmall = TextStyle(fontSize = 12.sp, fontWeight = FontWeight.Medium),
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
