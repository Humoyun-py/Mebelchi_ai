const projectCategories = ['cabinet', 'kitchen', 'wardrobe', 'tv_unit', 'bedroom', 'office', 'living', 'other'];

class ProjectCounts {
  const ProjectCounts({this.calculations = 0, this.cuttingLists = 0, this.designs = 0, this.images = 0, this.files = 0});
  final int calculations;
  final int cuttingLists;
  final int designs;
  final int images;
  final int files;

  int get total => calculations + cuttingLists + designs + images + files;

  factory ProjectCounts.fromJson(Object? j) {
    final m = j is Map ? j : const {};
    int n(String k) => (m[k] as num?)?.toInt() ?? 0;
    return ProjectCounts(calculations: n('calculations'), cuttingLists: n('cutting_lists'), designs: n('designs'), images: n('images'), files: n('files'));
  }
}

class Project {
  const Project({required this.id, required this.name, required this.description, required this.category, required this.status, required this.pinned, required this.counts, required this.updatedAt});
  final int id;
  final String name;
  final String description;
  final String category;
  final String status;
  final bool pinned;
  final ProjectCounts counts;
  final String updatedAt;

  bool get archived => status == 'archived';

  factory Project.fromJson(Map<String, dynamic> j) => Project(
        id: (j['id'] as num).toInt(),
        name: (j['name'] ?? '') as String,
        description: (j['description'] ?? '') as String,
        category: (j['category'] ?? 'other') as String,
        status: (j['status'] ?? 'active') as String,
        pinned: j['pinned'] == true,
        counts: ProjectCounts.fromJson(j['counts']),
        updatedAt: (j['updated_at'] ?? '') as String,
      );
}
