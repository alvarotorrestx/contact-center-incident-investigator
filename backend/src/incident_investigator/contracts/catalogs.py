from enum import StrEnum


class EvidenceSignal(StrEnum):
    SERVICE_LEVEL_DECLINE = "service_level_decline"
    ASA_INCREASE = "asa_increase"
    DEMAND_SURGE = "demand_surge"
    MODERATE_VOLUME_INCREASE = "moderate_volume_increase"
    ACTUAL_ABOVE_FORECAST = "actual_above_forecast"
    STABLE_DEMAND = "stable_demand"
    STABLE_STAFFING = "stable_staffing"
    LOGGED_IN_STAFFING_DROP = "logged_in_staffing_drop"
    PRODUCTIVE_STAFFING_DROP = "productive_staffing_drop"
    ADHERENCE_DECLINE = "adherence_decline"
    STABLE_HEADCOUNT = "stable_headcount"
    AHT_INCREASE = "aht_increase"
    TRANSFER_RATE_INCREASE = "transfer_rate_increase"
    ROUTING_CHANGE_EVENT = "routing_change_event"
    QUEUE_SERVICE_LEVEL_DIVERGENCE = "queue_service_level_divergence"
    QUEUE_STAFFING_IMBALANCE = "queue_staffing_imbalance"
    PLATFORM_EVENT = "platform_event"
    QUEUE_ACCUMULATION = "queue_accumulation"
    SERVICE_LEVEL_RECALCULATION_MISMATCH = "service_level_recalculation_mismatch"
    COUNT_CONSERVATION_MISMATCH = "count_conservation_mismatch"
    BRIEF_UNSUSTAINED_VARIANCE = "brief_unsustained_variance"
    NO_CORROBORATING_EVENT = "no_corroborating_event"


class ContributingFactor(StrEnum):
    MODERATE_VOLUME_INCREASE = "moderate_volume_increase"
    LOCALIZED_QUEUE_MISROUTING = "localized_queue_misrouting"


class CausalConcept(StrEnum):
    UNEXPECTED_DEMAND = "unexpected_demand"
    CAPACITY_DEFICIT = "capacity_deficit"
    STAFFING_SHORTFALL = "staffing_shortfall"
    ADHERENCE_DROP = "adherence_drop"
    REDUCED_PRODUCTIVE_STAFFING = "reduced_productive_staffing"
    ROUTING_CHANGE = "routing_change"
    INCREASED_TRANSFERS = "increased_transfers"
    INCREASED_AHT = "increased_aht"
    REDUCED_THROUGHPUT = "reduced_throughput"
    QUEUE_MISROUTING = "queue_misrouting"
    QUEUE_CAPACITY_IMBALANCE = "queue_capacity_imbalance"
    PLATFORM_INCIDENT = "platform_incident"
    CALL_PROCESSING_DISRUPTION = "call_processing_disruption"
    QUEUE_GROWTH = "queue_growth"
    SERVICE_LEVEL_DEGRADATION = "service_level_degradation"
    INCONSISTENT_REPORTED_METRIC = "inconsistent_reported_metric"
    DATA_QUALITY_ERROR = "data_quality_error"
    NORMAL_VARIANCE = "normal_variance"
    NO_SUSTAINED_IMPACT = "no_sustained_impact"
