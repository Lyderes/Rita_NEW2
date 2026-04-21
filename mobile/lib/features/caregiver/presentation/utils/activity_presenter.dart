
import 'package:rita_mobile/features/users/data/models/event_read.dart';

class ActivityDisplayModel {
  ActivityDisplayModel({required this.title, required this.subtitle});
  final String title;
  final String subtitle;
}

class ActivityPresenter {
  static ActivityDisplayModel getDisplayModel(UserEventRead event) {
    final type = event.eventType.toLowerCase();

    if (type.contains('user_speech')) {
      return _buildUserSpeechModel(event);
    }

    if (type.contains('assistant_response')) {
      return _buildAssistantResponseModel(event);
    }

    if (type.contains('checkin')) {
      return ActivityDisplayModel(
        title: 'Check-in realizado',
        subtitle: 'Todo parece estar en orden',
      );
    }

    if (type.contains('heartbeat') || type.contains('online')) {
      return ActivityDisplayModel(
        title: 'Dispositivo en línea',
        subtitle: 'El monitoreo está activo',
      );
    }

    if (type.contains('fall')) {
      return ActivityDisplayModel(
        title: '¡Evento de posible caída!',
        subtitle: 'Revisa el estado de la persona inmediatamente',
      );
    }

    if (type.contains('motion')) {
      return ActivityDisplayModel(
        title: 'Movimiento detectado',
        subtitle: 'Se registró actividad en la zona de monitoreo',
      );
    }

    if (type.contains('distress')) {
      return ActivityDisplayModel(
        title: 'Señal de malestar detectada',
        subtitle: 'Se identificaron palabras de desánimo o fatiga',
      );
    }

    if (type.contains('possible_fall') || type.contains('fall_suspected')) {
      return ActivityDisplayModel(
        title: 'Aviso de posible caída',
        subtitle: 'El sistema ha detectado una anomalía de movimiento',
      );
    }

    if (type.contains('wellbeing') || type.contains('health_concern')) {
      return ActivityDisplayModel(
        title: 'Aviso de estado de salud',
        subtitle: 'Análisis de bienestar completado con observaciones',
      );
    }

    if (type.contains('reminder_triggered')) {
      return ActivityDisplayModel(
        title: 'Aviso de rutina activado',
        subtitle: 'Se ha recordado una tarea programada',
      );
    }

    if (type.contains('reminder_confirmed')) {
      return ActivityDisplayModel(
        title: 'Rutina completada',
        subtitle: 'La persona ha confirmado la actividad',
      );
    }

    if (type.contains('pain_report')) {
      return ActivityDisplayModel(
        title: 'Reporte de dolor registrado',
        subtitle: 'Seguimiento de molestias físicas',
      );
    }

    // Fallback for any other type - strictly in Spanish
    return ActivityDisplayModel(
      title: event.eventType.replaceAll('_', ' ').toUpperCase(),
      subtitle: 'Actividad registrada en el diario',
    );
  }

  static ActivityDisplayModel _buildUserSpeechModel(UserEventRead event) {
    final text = (event.userText ?? '').toLowerCase();
    
    // Priority 1: Keyword/Context matching from text
    if (text.contains('mareada') || text.contains('mareo')) {
      return ActivityDisplayModel(
        title: 'Comentó que se encontraba mareada',
        subtitle: 'Detectado en la conversación con RITA',
      );
    }
    
    if (text.contains('duele') || text.contains('dolor')) {
      return ActivityDisplayModel(
        title: 'Comentó que sentía dolor',
        subtitle: 'Registrado durante el seguimiento de hoy',
      );
    }
    
    if (text.contains('mal') || text.contains('triste') || text.contains('cansada')) {
      return ActivityDisplayModel(
        title: 'Se detectó una señal de malestar',
        subtitle: 'Análisis de estado de ánimo: Bajo',
      );
    }

    // Default for user speech
    return ActivityDisplayModel(
      title: 'Habló con RITA',
      subtitle: event.userText != null && event.userText!.isNotEmpty 
          ? 'Transcripción: "${_truncate(event.userText!)}"'
          : 'La conversación fue registrada correctamente',
    );
  }

  static ActivityDisplayModel _buildAssistantResponseModel(UserEventRead event) {
    final text = (event.ritaText ?? '').toLowerCase();
    
    if (text.contains('hola') || text.contains('buenos días') || text.contains('qué tal')) {
      return ActivityDisplayModel(
        title: 'RITA inició una conversación',
        subtitle: 'Saludo y seguimiento matutino',
      );
    }
    
    if (text.contains('siento') || text.contains('ayudar') || text.contains('aliviar')) {
      return ActivityDisplayModel(
        title: 'RITA ofreció apoyo emocional',
        subtitle: 'Respuesta empática ante malestar',
      );
    }

    return ActivityDisplayModel(
      title: 'RITA respondió con normalidad',
      subtitle: event.ritaText != null && event.ritaText!.isNotEmpty 
          ? 'Mensaje: "${_truncate(event.ritaText!)}"'
          : 'Interacción de seguimiento completada',
    );
  }

  static String _truncate(String text, {int length = 40}) {
    if (text.length <= length) return text;
    return '${text.substring(0, length)}...';
  }
}
