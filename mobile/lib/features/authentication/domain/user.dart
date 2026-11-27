enum UserRole {
  homeowner,
  maker,
  workshop;

  static UserRole parse(String? v) => switch (v) {
        'maker' => UserRole.maker,
        'workshop' => UserRole.workshop,
        _ => UserRole.homeowner,
      };

  String get apiValue => name;
}

class User {
  const User({
    required this.id,
    required this.email,
    required this.firstName,
    required this.lastName,
    required this.phone,
    required this.phoneVerified,
    required this.avatarUrl,
    required this.role,
    required this.roleSelected,
    required this.language,
    required this.isAdmin,
  });

  final int id;
  final String email;
  final String firstName;
  final String lastName;
  final String phone;
  final bool phoneVerified;
  final String? avatarUrl; // relative, signed, short-lived
  final UserRole role;
  final bool roleSelected;
  final String language;
  final bool isAdmin;

  String get fullName => '$firstName $lastName'.trim();

  /// A workshop account is created by an administrator, so it never has to pick a role; staff neither.
  bool get needsRole => !roleSelected && role != UserRole.workshop && !isAdmin;

  factory User.fromJson(Map<String, dynamic> j) => User(
        id: (j['id'] as num).toInt(),
        email: (j['email'] ?? '') as String,
        firstName: (j['first_name'] ?? '') as String,
        lastName: (j['last_name'] ?? '') as String,
        phone: (j['phone'] ?? '') as String,
        phoneVerified: j['phone_verified'] == true,
        avatarUrl: j['avatar_url'] as String?,
        role: UserRole.parse(j['role'] as String?),
        roleSelected: j['role_selected'] == true,
        language: (j['language'] ?? 'en') as String,
        isAdmin: j['is_admin'] == true,
      );
}
