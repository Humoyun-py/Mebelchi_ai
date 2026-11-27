class FurnitureImage {
  const FurnitureImage(this.view, this.url);
  final String view;
  final String url;
}

class Furniture {
  const Furniture({
    required this.id,
    required this.slug,
    required this.category,
    required this.name,
    required this.description,
    required this.width,
    required this.height,
    required this.depth,
    required this.price,
    required this.currency,
    required this.material,
    required this.color,
    required this.workshopName,
    required this.leadTimeDays,
    required this.isAvailable,
    required this.images,
    required this.modelSource,
  });

  final int id;
  final String slug;
  final String category;
  final String name;
  final String description;
  final double? width;
  final double? height;
  final double? depth;
  final String? price; // decimal string exactly as the server sent it; never computed on the phone
  final String currency;
  final String material;
  final String color;
  final String? workshopName;
  final int? leadTimeDays;
  final bool isAvailable;
  final List<FurnitureImage> images;
  final String modelSource;

  factory Furniture.fromJson(Map<String, dynamic> j) {
    final d = j['defaults'] is Map ? Map<String, dynamic>.from(j['defaults'] as Map) : <String, dynamic>{};
    double? n(Object? v) => v is num ? v.toDouble() : null;
    return Furniture(
      id: (j['id'] as num).toInt(),
      slug: (j['slug'] ?? '') as String,
      category: (j['category'] ?? '') as String,
      name: (j['name'] ?? '') as String,
      description: (j['description'] ?? '') as String,
      width: n(d['width']),
      height: n(d['height']),
      depth: n(d['depth']),
      price: j['price']?.toString(),
      currency: (j['currency'] ?? '') as String,
      material: (j['material'] ?? '') as String,
      color: (j['color'] ?? '') as String,
      workshopName: j['workshop_name'] as String?,
      leadTimeDays: (j['lead_time_days'] as num?)?.toInt(),
      isAvailable: j['is_available'] != false,
      images: ((j['images'] as List?) ?? const []).map((e) => FurnitureImage((e as Map)['view'] as String, e['url'] as String)).toList(),
      modelSource: (j['model_source'] ?? '') as String,
    );
  }

  String get dimensions => '${width?.round() ?? '?'} x ${depth?.round() ?? '?'} x ${height?.round() ?? '?'} mm';
}
