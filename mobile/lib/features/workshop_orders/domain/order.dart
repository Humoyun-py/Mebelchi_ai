/// Statuses the server knows. The app never decides what is allowed: it shows the buttons for `allowedNext`, which the server computes.
const orderStatuses = ['new', 'pending', 'confirmed', 'rejected', 'in_production', 'quality_check', 'ready', 'delivery', 'delivered', 'cancelled'];

/// The order buttons are shown in: the forward steps first, then reject, and "cancel" last. The server lists the allowed moves alphabetically.
const _actionPriority = ['confirmed', 'in_production', 'quality_check', 'ready', 'delivery', 'delivered', 'rejected', 'cancelled'];

List<String> sortedActions(List<String> allowed) {
  int rank(String s) {
    final i = _actionPriority.indexOf(s);
    return i < 0 ? _actionPriority.length : i;
  }

  return [...allowed]..sort((a, b) => rank(a).compareTo(rank(b)));
}

/// Filter chips of the list (a single server-side `status` filter each).
const orderFilters = ['', 'pending', 'confirmed', 'in_production', 'ready', 'delivered'];

/// Moves that must come with a written reason.
const statusesNeedingReason = {'rejected'};
const statusesAskingConfirmation = {'rejected', 'cancelled'};

class StatusChange {
  const StatusChange({required this.from, required this.to, required this.note, required this.at});
  final String from;
  final String to;
  final String note;
  final String at;

  factory StatusChange.fromJson(Map<String, dynamic> j) => StatusChange(
        from: (j['from_status'] ?? '') as String,
        to: (j['to_status'] ?? '') as String,
        note: (j['note'] ?? '') as String,
        at: (j['created_at'] ?? '') as String,
      );
}

class WorkshopOrder {
  const WorkshopOrder({
    required this.id,
    required this.number,
    required this.title,
    required this.description,
    required this.customerName,
    required this.customerPhone,
    required this.customerAddress,
    required this.status,
    required this.allowedNext,
    this.totalPrice,
    this.paidAmount,
    this.paymentStatus = '',
    this.deadline = '',
    this.createdAt = '',
    this.rejectionReason = '',
    this.history = const [],
  });

  final int id;
  final String number;
  final String title;
  final String description;
  final String customerName;
  final String customerPhone;
  final String customerAddress;
  final String status;
  final List<String> allowedNext;
  final String? totalPrice; // absent for employees: the server never sends money fields to them
  final String? paidAmount;
  final String paymentStatus;
  final String deadline;
  final String createdAt;
  final String rejectionReason;
  final List<StatusChange> history;

  bool get waitingForAnswer => status == 'pending';

  factory WorkshopOrder.fromJson(Map<String, dynamic> j) => WorkshopOrder(
        id: (j['id'] as num).toInt(),
        number: (j['order_number'] ?? '') as String,
        title: (j['title'] ?? '') as String,
        description: (j['description'] ?? '') as String,
        customerName: (j['customer_name'] ?? '') as String,
        customerPhone: (j['customer_phone'] ?? '') as String,
        customerAddress: (j['customer_address'] ?? '') as String,
        status: (j['status'] ?? 'new') as String,
        allowedNext: [for (final s in (j['allowed_next_statuses'] as List? ?? const [])) '$s'],
        totalPrice: j['total_price']?.toString(),
        paidAmount: j['paid_amount']?.toString(),
        paymentStatus: (j['payment_status'] ?? '') as String,
        deadline: (j['deadline'] ?? '') as String,
        createdAt: (j['created_at'] ?? '') as String,
        rejectionReason: (j['rejection_reason'] ?? '') as String,
        history: [for (final h in (j['status_history'] as List? ?? const [])) StatusChange.fromJson(Map<String, dynamic>.from(h as Map))],
      );
}
