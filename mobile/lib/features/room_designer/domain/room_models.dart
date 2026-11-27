/// The server sends texts as `{"en":..., "uz":..., "ru":...}`; this picks the user's language.
String loc(Object? v, String lang) {
  if (v is Map) {
    final s = v[lang] ?? v['en'] ?? (v.values.isEmpty ? '' : v.values.first);
    return s?.toString() ?? '';
  }
  return v?.toString() ?? '';
}

typedef Json = Map<String, dynamic>;

Json asJson(Object? v) => v is Map ? Map<String, dynamic>.from(v) : <String, dynamic>{};
List<Json> asJsonList(Object? v) => v is List ? v.map(asJson).toList() : <Json>[];

class RoomBrief {
  const RoomBrief({required this.id, required this.status, required this.step, required this.goal, required this.updatedAt});
  final int id;
  final String status;
  final String step;
  final String? goal;
  final String updatedAt;

  factory RoomBrief.fromJson(Json j) => RoomBrief(
        id: (j['id'] as num).toInt(),
        status: (j['status'] ?? '') as String,
        step: (j['step'] ?? '') as String,
        goal: j['goal'] as String?,
        updatedAt: (j['updated_at'] ?? '') as String,
      );
}

/// One room-design conversation as the API returns it. [question] is the server's description of the current step.
class RoomFlow {
  const RoomFlow({required this.id, required this.status, required this.step, required this.question, required this.designId, required this.config, required this.warnings, required this.updatedAt, this.unknownModels = const []});
  final int id;
  final String status;
  final String step;
  final Json question;
  final int? designId;
  final Json? config;
  final List<Json> warnings;
  final String updatedAt;
  final List<String> unknownModels;

  bool get isActive => status == 'active';
  bool get hasRoom => config != null;
  List<Json> get items => asJsonList(config?['items']);
  Json get room => asJson(config?['room']);
  Json get colors => asJson(config?['colors']);

  factory RoomFlow.fromJson(Json j) {
    final room = j['room'];
    final roomMap = room is Map ? asJson(room) : null;
    return RoomFlow(
      id: (j['id'] as num).toInt(),
      status: (j['status'] ?? '') as String,
      step: (j['step'] ?? '') as String,
      question: asJson(j['question']),
      designId: (j['design'] as num?)?.toInt(),
      config: roomMap == null ? null : asJson(roomMap['config']),
      warnings: roomMap == null ? const [] : asJsonList(roomMap['warnings']),
      updatedAt: (j['updated_at'] ?? '') as String,
      unknownModels: ((j['unknown_models'] as List?) ?? const []).map((e) => e.toString()).toList(),
    );
  }
}
