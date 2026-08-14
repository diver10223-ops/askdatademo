package com.askdata.platform.multitask.contract;

import java.util.Map;
import java.util.Set;

public final class StateTransitions {
    private static final Map<PlanStatus, Set<PlanStatus>> PLANS = Map.of(
            PlanStatus.DRAFT, Set.of(PlanStatus.VALIDATED, PlanStatus.INVALID, PlanStatus.CANCELLED),
            PlanStatus.VALIDATED, Set.of(PlanStatus.WAITING_CONFIRMATION, PlanStatus.CONFIRMED, PlanStatus.CANCELLED),
            PlanStatus.WAITING_CONFIRMATION, Set.of(PlanStatus.CONFIRMED, PlanStatus.CANCELLED),
            PlanStatus.CONFIRMED, Set.of(PlanStatus.EXECUTING, PlanStatus.CANCELLED),
            PlanStatus.EXECUTING, Set.of(PlanStatus.COMPLETED, PlanStatus.CANCELLED));
    private static final Map<NodeStatus, Set<NodeStatus>> NODES = Map.ofEntries(
            Map.entry(NodeStatus.WAITING, Set.of(NodeStatus.READY, NodeStatus.SKIPPED, NodeStatus.CANCELLED)),
            Map.entry(NodeStatus.READY, Set.of(NodeStatus.QUEUED, NodeStatus.CANCELLED)),
            Map.entry(NodeStatus.QUEUED, Set.of(NodeStatus.RUNNING, NodeStatus.CANCELLED)),
            Map.entry(NodeStatus.RUNNING, Set.of(NodeStatus.SUCCEEDED, NodeStatus.FAILED, NodeStatus.RETRY_WAIT, NodeStatus.CANCELLATION_REQUESTED, NodeStatus.TIMED_OUT)),
            Map.entry(NodeStatus.RETRY_WAIT, Set.of(NodeStatus.READY, NodeStatus.CANCELLED)),
            Map.entry(NodeStatus.CANCELLATION_REQUESTED, Set.of(NodeStatus.CANCELLED, NodeStatus.SUCCEEDED, NodeStatus.FAILED)));
    private static final Map<AttemptStatus, Set<AttemptStatus>> ATTEMPTS = Map.of(
            AttemptStatus.PENDING, Set.of(AttemptStatus.RUNNING, AttemptStatus.CANCELLED),
            AttemptStatus.RUNNING, Set.of(AttemptStatus.SUCCEEDED, AttemptStatus.FAILED, AttemptStatus.CANCELLED, AttemptStatus.TIMED_OUT));
    private static final Map<RequestStatus, Set<RequestStatus>> REQUESTS = Map.ofEntries(
            Map.entry(RequestStatus.PENDING, Set.of(RequestStatus.WAITING_CONFIRMATION, RequestStatus.QUEUED, RequestStatus.CANCELLED)),
            Map.entry(RequestStatus.WAITING_CONFIRMATION, Set.of(RequestStatus.QUEUED, RequestStatus.CANCELLED)),
            Map.entry(RequestStatus.QUEUED, Set.of(RequestStatus.RUNNING, RequestStatus.CANCELLATION_REQUESTED, RequestStatus.CANCELLED)),
            Map.entry(RequestStatus.RUNNING, Set.of(RequestStatus.PARTIAL_SUCCESS, RequestStatus.SUCCEEDED, RequestStatus.FAILED, RequestStatus.CANCELLATION_REQUESTED, RequestStatus.TIMED_OUT)),
            Map.entry(RequestStatus.CANCELLATION_REQUESTED, Set.of(RequestStatus.CANCELLED, RequestStatus.PARTIAL_SUCCESS, RequestStatus.SUCCEEDED, RequestStatus.FAILED)));

    private StateTransitions() {}

    public static boolean allows(PlanStatus from, PlanStatus to) { return PLANS.getOrDefault(from, Set.of()).contains(to); }
    public static boolean allows(NodeStatus from, NodeStatus to) { return NODES.getOrDefault(from, Set.of()).contains(to); }
    public static boolean allows(AttemptStatus from, AttemptStatus to) { return ATTEMPTS.getOrDefault(from, Set.of()).contains(to); }
    public static boolean allows(RequestStatus from, RequestStatus to) { return REQUESTS.getOrDefault(from, Set.of()).contains(to); }
}
