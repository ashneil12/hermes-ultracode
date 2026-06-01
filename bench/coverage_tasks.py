"""Deep-research COVERAGE tasks: broad questions with a rich rubric of sub-points.

Unlike research_tasks.py (closed-form recall, which a single pass saturates), these
are broad multi-facet questions where a single shot spreads attention thin and drops
the long tail. The metric is COVERAGE = fraction of rubric points present in the
synthesized answer. Each rubric point requires concept + mechanism keywords (not a
bare name-drop) so keyword-stuffing can't game it. Facets are informational (printed,
not scored) — they show the decomposition the orchestrator should discover.
"""

from bench.tasks import Bug, BugTask  # a rubric point == Bug(name, "rubric", signatures)

# signatures = OR of (AND of keywords): inner list = all must substring-match; outer = any variant.

_CONSENSUS = BugTask(
    id="consensus",
    prompt=("Give a comprehensive technical overview of distributed consensus algorithms: the major "
            "families, how each works, the fault models they tolerate, and the tradeoffs between them."),
    code="",
    facets=["leader-based (Raft)", "classical (Paxos)", "Byzantine (PBFT)",
            "blockchain (PoW/PoS)", "commit protocols & quorums", "tradeoffs & bounds"],
    planted=[
        Bug("raft_leader_election", "rubric", [["raft", "leader", "election"], ["raft", "term"]]),
        Bug("raft_log_replication", "rubric", [["raft", "log", "replicat"], ["raft", "append", "entr"]]),
        Bug("paxos_roles", "rubric", [["proposer", "acceptor"], ["paxos", "acceptor"], ["multi-paxos"]]),
        Bug("pbft_byzantine", "rubric", [["pbft"], ["practical byzantine"], ["byzantine", "fault", "toleran"]]),
        Bug("bft_bound", "rubric", [["3f+1"], ["f < n/3"], ["less than n/3"], ["one-third", "faulty"], ["n/3", "byzantine"]]),
        Bug("two_phase_commit", "rubric", [["two-phase commit"], ["2pc"], ["prepare", "commit", "abort"]]),
        Bug("quorum", "rubric", [["quorum"], ["majority", "vote"], ["w + r > n"]]),
        Bug("proof_of_work", "rubric", [["proof of work"], ["proof-of-work"], ["mining", "hash"]]),
        Bug("proof_of_stake", "rubric", [["proof of stake"], ["proof-of-stake"], ["validator", "stake"]]),
        Bug("latency_throughput", "rubric", [["latency", "throughput"], ["performance", "tradeoff"]]),
        Bug("raft_systems", "rubric", [["etcd"], ["consul"], ["zookeeper"], ["zab"]]),
        Bug("blockchain_examples", "rubric", [["bitcoin"], ["ethereum"], ["nakamoto"]]),
        Bug("safety_liveness", "rubric", [["safety", "liveness"], ["flp"], ["asynchron", "impossib"]]),
    ],
)

_MICROSERVICES = BugTask(
    id="microservices",
    prompt=("Give a comprehensive overview of microservices architecture: how to decompose services, "
            "how they communicate, how to keep data consistent, how to make them resilient, how to "
            "observe them, and how they are deployed and scaled."),
    code="",
    facets=["decomposition", "communication", "data consistency", "resilience",
            "observability", "deployment & scaling"],
    planted=[
        Bug("bounded_context", "rubric", [["bounded context"], ["domain-driven"], ["domain driven design"]]),
        Bug("coupling_cohesion", "rubric", [["coupling", "cohesion"], ["loose", "coupl"]]),
        Bug("sync_rest_rpc", "rubric", [["rest", "synchronous"], ["grpc"], ["rest", "api", "http"]]),
        Bug("async_messaging", "rubric", [["message queue"], ["event", "asynchronous"], ["kafka"], ["pub/sub"], ["publish", "subscribe"]]),
        Bug("saga", "rubric", [["saga"], ["distributed transaction"], ["compensating transaction"]]),
        Bug("eventual_consistency", "rubric", [["eventual", "consisten"], ["eventually consistent"]]),
        Bug("circuit_breaker", "rubric", [["circuit breaker"]]),
        Bug("bulkhead", "rubric", [["bulkhead"]]),
        Bug("retry_backoff", "rubric", [["retry", "backoff"], ["exponential backoff"]]),
        Bug("timeout", "rubric", [["timeout"], ["deadline"]]),
        Bug("distributed_tracing", "rubric", [["distributed tracing"], ["trace", "span"], ["opentelemetry"], ["jaeger"]]),
        Bug("metrics", "rubric", [["metrics"], ["prometheus"], ["instrument"]]),
        Bug("service_discovery", "rubric", [["service discovery"], ["service registry"], ["dns", "discover"]]),
        Bug("service_mesh", "rubric", [["service mesh"], ["sidecar"], ["istio"], ["envoy"]]),
        Bug("orchestration_scaling", "rubric", [["kubernetes"], ["container", "orchestrat"], ["autoscal"], ["horizontal", "scal"]]),
    ],
)

_SECURITY = BugTask(
    id="appsec",
    prompt=("Give a comprehensive overview of application and infrastructure security: authentication, "
            "authorization, cryptography, common web vulnerabilities and defenses, transport security, "
            "secrets/identity management, and compliance."),
    code="",
    facets=["authentication", "authorization", "cryptography", "web vulns & defenses",
            "transport security", "secrets/identity & compliance"],
    planted=[
        Bug("oauth_oidc", "rubric", [["oauth"], ["openid connect"], ["oidc"]]),
        Bug("jwt", "rubric", [["jwt"], ["json web token"], ["bearer token"]]),
        Bug("mfa", "rubric", [["multi-factor"], ["multi factor"], ["mfa"], ["2fa"], ["two-factor"]]),
        Bug("rbac", "rubric", [["rbac"], ["role-based", "access"], ["role based access"]]),
        Bug("abac", "rubric", [["abac"], ["attribute-based", "access"], ["attribute based access"]]),
        Bug("zero_trust", "rubric", [["zero trust"], ["zero-trust"]]),
        Bug("symmetric_crypto", "rubric", [["aes"], ["symmetric", "encrypt"]]),
        Bug("asymmetric_crypto", "rubric", [["rsa"], ["elliptic curve"], ["ecc"], ["asymmetric", "key"], ["public key", "private key"]]),
        Bug("hashing", "rubric", [["sha-256"], ["sha256"], ["bcrypt"], ["hash", "password"]]),
        Bug("digital_signature", "rubric", [["digital signature"], ["signature", "verify", "certificate"]]),
        Bug("sql_injection", "rubric", [["sql injection"], ["sqli"], ["parameteriz", "query"], ["prepared statement"]]),
        Bug("xss", "rubric", [["xss"], ["cross-site scripting"], ["output encoding"]]),
        Bug("csrf", "rubric", [["csrf"], ["cross-site request forgery"], ["anti-forgery token"]]),
        Bug("tls_handshake", "rubric", [["tls", "handshake"], ["tls", "cipher"], ["ssl/tls"]]),
        Bug("mtls", "rubric", [["mutual tls"], ["mtls"], ["certificate pinning"]]),
        Bug("iam_roles", "rubric", [["iam", "role"], ["least privilege"], ["aws iam"]]),
        Bug("secrets_mgmt", "rubric", [["secrets management"], ["vault"], ["key management", "kms"], ["secret", "rotat"]]),
        Bug("compliance", "rubric", [["gdpr"], ["pci"], ["soc 2"], ["hipaa"], ["compliance"]]),
    ],
)

COVERAGE_TASKS = [_CONSENSUS, _MICROSERVICES, _SECURITY]
