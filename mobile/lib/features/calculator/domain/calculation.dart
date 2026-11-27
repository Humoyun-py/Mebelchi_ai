const cabinetTypes = ['standard', 'kitchen_base', 'kitchen_wall', 'sliding_wardrobe'];
const handleStyles = ['bar', 'knob', 'none'];

/// What the user types. Only fields the server's engine accepts; the server validates ranges and answers with field errors.
class CabinetInput {
  const CabinetInput({
    required this.width,
    required this.height,
    required this.depth,
    this.thickness = 18,
    this.shelves = 0,
    this.doors = 0,
    this.drawers = 0,
    this.material = 'MDF',
    this.cabinetType = 'standard',
    this.handleStyle = 'bar',
    this.edgeThickness = 0,
  });

  final double width;
  final double height;
  final double depth;
  final double thickness;
  final int shelves;
  final int doors;
  final int drawers;
  final String material;
  final String cabinetType;
  final String handleStyle;
  final double edgeThickness;

  Map<String, dynamic> toJson() => {
        'width': width,
        'height': height,
        'depth': depth,
        'thickness': thickness,
        'shelves': shelves,
        'doors': doors,
        'drawers': drawers,
        'material': material,
        'cabinet_type': cabinetType,
        'handle_style': handleStyle,
        'edge_thickness': edgeThickness,
      };
}

class CalcPart {
  const CalcPart({required this.name, required this.width, required this.height, required this.thickness, required this.quantity, required this.material});
  final String name;
  final double width;
  final double height;
  final double thickness;
  final int quantity;
  final String material;

  factory CalcPart.fromJson(Map<String, dynamic> j) => CalcPart(
        name: (j['name'] ?? '') as String,
        width: (j['width'] as num?)?.toDouble() ?? 0,
        height: (j['height'] as num?)?.toDouble() ?? 0,
        thickness: (j['thickness'] as num?)?.toDouble() ?? 0,
        quantity: (j['quantity'] as num?)?.toInt() ?? 0,
        material: (j['material'] ?? '') as String,
      );
}

class HardwareItem {
  const HardwareItem({required this.name, required this.quantity, required this.note});
  final String name;
  final int quantity;
  final String note;

  factory HardwareItem.fromJson(Map<String, dynamic> j) => HardwareItem(
        name: (j['name'] ?? '') as String,
        quantity: (j['quantity'] as num?)?.toInt() ?? 0,
        note: (j['note'] ?? '') as String,
      );
}

class MaterialUse {
  const MaterialUse({required this.label, required this.areaM2, required this.withWasteM2, required this.parts});
  final String label;
  final double areaM2;
  final double withWasteM2;
  final int parts;
}

/// The engine's answer. Everything shown is exactly what the server returned; the app computes nothing.
class CalcResult {
  const CalcResult({
    required this.panelCount,
    required this.totalAreaM2,
    required this.edgeBandingM,
    required this.materials,
    required this.parts,
    required this.hardware,
    required this.warnings,
    required this.assumptions,
    required this.disclaimer,
    this.savedId,
  });

  final int panelCount;
  final double totalAreaM2;
  final double edgeBandingM;
  final List<MaterialUse> materials;
  final List<CalcPart> parts;
  final List<HardwareItem> hardware;
  final List<String> warnings;
  final List<String> assumptions;
  final String disclaimer;
  final int? savedId;

  CalcResult withSavedId(int id) => CalcResult(
        panelCount: panelCount,
        totalAreaM2: totalAreaM2,
        edgeBandingM: edgeBandingM,
        materials: materials,
        parts: parts,
        hardware: hardware,
        warnings: warnings,
        assumptions: assumptions,
        disclaimer: disclaimer,
        savedId: id,
      );

  factory CalcResult.fromJson(Map<String, dynamic> j) {
    final summary = Map<String, dynamic>.from((j['summary'] ?? const {}) as Map);
    final by = Map<String, dynamic>.from((summary['by_material'] ?? const {}) as Map);
    List<Map<String, dynamic>> maps(Object? v) => [for (final e in (v as List? ?? const [])) Map<String, dynamic>.from(e as Map)];
    return CalcResult(
      panelCount: (summary['panel_count'] as num?)?.toInt() ?? 0,
      totalAreaM2: (summary['total_area_m2'] as num?)?.toDouble() ?? 0,
      edgeBandingM: (summary['edge_banding_m'] as num?)?.toDouble() ?? 0,
      materials: [
        for (final e in by.entries)
          MaterialUse(
            label: e.key,
            areaM2: ((e.value as Map)['area_m2'] as num?)?.toDouble() ?? 0,
            withWasteM2: ((e.value as Map)['estimated_area_with_waste_m2'] as num?)?.toDouble() ?? 0,
            parts: ((e.value as Map)['parts'] as num?)?.toInt() ?? 0,
          ),
      ],
      parts: [for (final p in maps(j['parts'])) CalcPart.fromJson(p)],
      hardware: [for (final h in maps(j['hardware'])) HardwareItem.fromJson(h)],
      warnings: [for (final w in (j['warnings'] as List? ?? const [])) '$w'],
      assumptions: [for (final a in (j['assumptions'] as List? ?? const [])) '$a'],
      disclaimer: (j['disclaimer'] ?? '') as String,
      savedId: (j['saved_id'] as num?)?.toInt(),
    );
  }
}

/// The result of optimising a cutting list (sheets needed and how much of them is used).
class CuttingSummary {
  const CuttingSummary({required this.listId, required this.sheetCount, required this.utilizationPct});
  final int listId;
  final int sheetCount;
  final double utilizationPct;
}
