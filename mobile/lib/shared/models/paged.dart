/// DRF page envelope: `{count, next, previous, results}`. Used by every list endpoint in later phases.
class Paged<T> {
  const Paged({required this.count, required this.results, this.next, this.previous});
  final int count;
  final String? next;
  final String? previous;
  final List<T> results;

  bool get hasMore => next != null;

  factory Paged.fromJson(Map<String, dynamic> json, T Function(Map<String, dynamic>) item) => Paged(
        count: (json['count'] as num?)?.toInt() ?? 0,
        next: json['next'] as String?,
        previous: json['previous'] as String?,
        results: ((json['results'] as List?) ?? const []).map((e) => item(Map<String, dynamic>.from(e as Map))).toList(),
      );
}
