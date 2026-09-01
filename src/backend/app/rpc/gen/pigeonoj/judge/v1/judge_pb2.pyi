from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class ServerMessage(_message.Message):
    __slots__ = ("ack", "job", "cancel", "run_code")
    ACK_FIELD_NUMBER: _ClassVar[int]
    JOB_FIELD_NUMBER: _ClassVar[int]
    CANCEL_FIELD_NUMBER: _ClassVar[int]
    RUN_CODE_FIELD_NUMBER: _ClassVar[int]
    ack: RegisterAck
    job: SubmitJob
    cancel: CancelJob
    run_code: RunCodeJob
    def __init__(self, ack: _Optional[_Union[RegisterAck, _Mapping]] = ..., job: _Optional[_Union[SubmitJob, _Mapping]] = ..., cancel: _Optional[_Union[CancelJob, _Mapping]] = ..., run_code: _Optional[_Union[RunCodeJob, _Mapping]] = ...) -> None: ...

class RegisterAck(_message.Message):
    __slots__ = ("node_id", "heartbeat_interval_seconds")
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_INTERVAL_SECONDS_FIELD_NUMBER: _ClassVar[int]
    node_id: str
    heartbeat_interval_seconds: int
    def __init__(self, node_id: _Optional[str] = ..., heartbeat_interval_seconds: _Optional[int] = ...) -> None: ...

class ResourceLimits(_message.Message):
    __slots__ = ("time_limit_ms", "memory_limit_mb", "output_limit_kb", "process_limit", "cpu_cores")
    TIME_LIMIT_MS_FIELD_NUMBER: _ClassVar[int]
    MEMORY_LIMIT_MB_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_LIMIT_KB_FIELD_NUMBER: _ClassVar[int]
    PROCESS_LIMIT_FIELD_NUMBER: _ClassVar[int]
    CPU_CORES_FIELD_NUMBER: _ClassVar[int]
    time_limit_ms: int
    memory_limit_mb: int
    output_limit_kb: int
    process_limit: int
    cpu_cores: int
    def __init__(self, time_limit_ms: _Optional[int] = ..., memory_limit_mb: _Optional[int] = ..., output_limit_kb: _Optional[int] = ..., process_limit: _Optional[int] = ..., cpu_cores: _Optional[int] = ...) -> None: ...

class TestCaseFile(_message.Message):
    __slots__ = ("test_case_id", "name", "score")
    TEST_CASE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    test_case_id: str
    name: str
    score: int
    def __init__(self, test_case_id: _Optional[str] = ..., name: _Optional[str] = ..., score: _Optional[int] = ...) -> None: ...

class SubmitJob(_message.Message):
    __slots__ = ("submission_id", "language", "code", "limits", "problem_id", "data_version", "spj", "cases", "stop_on_failure")
    SUBMISSION_ID_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    PROBLEM_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_VERSION_FIELD_NUMBER: _ClassVar[int]
    SPJ_FIELD_NUMBER: _ClassVar[int]
    CASES_FIELD_NUMBER: _ClassVar[int]
    STOP_ON_FAILURE_FIELD_NUMBER: _ClassVar[int]
    submission_id: str
    language: str
    code: bytes
    limits: ResourceLimits
    problem_id: str
    data_version: str
    spj: bool
    cases: _containers.RepeatedCompositeFieldContainer[TestCaseFile]
    stop_on_failure: bool
    def __init__(self, submission_id: _Optional[str] = ..., language: _Optional[str] = ..., code: _Optional[bytes] = ..., limits: _Optional[_Union[ResourceLimits, _Mapping]] = ..., problem_id: _Optional[str] = ..., data_version: _Optional[str] = ..., spj: _Optional[bool] = ..., cases: _Optional[_Iterable[_Union[TestCaseFile, _Mapping]]] = ..., stop_on_failure: _Optional[bool] = ...) -> None: ...

class CancelJob(_message.Message):
    __slots__ = ("submission_id",)
    SUBMISSION_ID_FIELD_NUMBER: _ClassVar[int]
    submission_id: str
    def __init__(self, submission_id: _Optional[str] = ...) -> None: ...

class RunCodeJob(_message.Message):
    __slots__ = ("request_id", "language", "code", "input", "limits")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    LANGUAGE_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    INPUT_FIELD_NUMBER: _ClassVar[int]
    LIMITS_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    language: str
    code: bytes
    input: bytes
    limits: ResourceLimits
    def __init__(self, request_id: _Optional[str] = ..., language: _Optional[str] = ..., code: _Optional[bytes] = ..., input: _Optional[bytes] = ..., limits: _Optional[_Union[ResourceLimits, _Mapping]] = ...) -> None: ...

class RunCodeResult(_message.Message):
    __slots__ = ("request_id", "status", "output", "error_message", "time_used_ms", "memory_used_kb")
    REQUEST_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    TIME_USED_MS_FIELD_NUMBER: _ClassVar[int]
    MEMORY_USED_KB_FIELD_NUMBER: _ClassVar[int]
    request_id: str
    status: str
    output: bytes
    error_message: str
    time_used_ms: int
    memory_used_kb: int
    def __init__(self, request_id: _Optional[str] = ..., status: _Optional[str] = ..., output: _Optional[bytes] = ..., error_message: _Optional[str] = ..., time_used_ms: _Optional[int] = ..., memory_used_kb: _Optional[int] = ...) -> None: ...

class NodeMessage(_message.Message):
    __slots__ = ("register", "heartbeat", "result", "run_code_result")
    REGISTER_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_FIELD_NUMBER: _ClassVar[int]
    RESULT_FIELD_NUMBER: _ClassVar[int]
    RUN_CODE_RESULT_FIELD_NUMBER: _ClassVar[int]
    register: Register
    heartbeat: Heartbeat
    result: JudgeResult
    run_code_result: RunCodeResult
    def __init__(self, register: _Optional[_Union[Register, _Mapping]] = ..., heartbeat: _Optional[_Union[Heartbeat, _Mapping]] = ..., result: _Optional[_Union[JudgeResult, _Mapping]] = ..., run_code_result: _Optional[_Union[RunCodeResult, _Mapping]] = ...) -> None: ...

class Register(_message.Message):
    __slots__ = ("token", "node_id", "name", "capacity", "version")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    NODE_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    CAPACITY_FIELD_NUMBER: _ClassVar[int]
    VERSION_FIELD_NUMBER: _ClassVar[int]
    token: str
    node_id: str
    name: str
    capacity: int
    version: str
    def __init__(self, token: _Optional[str] = ..., node_id: _Optional[str] = ..., name: _Optional[str] = ..., capacity: _Optional[int] = ..., version: _Optional[str] = ...) -> None: ...

class Heartbeat(_message.Message):
    __slots__ = ("running_tasks", "cpu_usage", "memory_usage")
    RUNNING_TASKS_FIELD_NUMBER: _ClassVar[int]
    CPU_USAGE_FIELD_NUMBER: _ClassVar[int]
    MEMORY_USAGE_FIELD_NUMBER: _ClassVar[int]
    running_tasks: int
    cpu_usage: int
    memory_usage: int
    def __init__(self, running_tasks: _Optional[int] = ..., cpu_usage: _Optional[int] = ..., memory_usage: _Optional[int] = ...) -> None: ...

class CaseResult(_message.Message):
    __slots__ = ("test_case_id", "status", "time_used_ms", "memory_used_kb", "score", "output")
    TEST_CASE_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    TIME_USED_MS_FIELD_NUMBER: _ClassVar[int]
    MEMORY_USED_KB_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    OUTPUT_FIELD_NUMBER: _ClassVar[int]
    test_case_id: str
    status: str
    time_used_ms: int
    memory_used_kb: int
    score: int
    output: bytes
    def __init__(self, test_case_id: _Optional[str] = ..., status: _Optional[str] = ..., time_used_ms: _Optional[int] = ..., memory_used_kb: _Optional[int] = ..., score: _Optional[int] = ..., output: _Optional[bytes] = ...) -> None: ...

class JudgeResult(_message.Message):
    __slots__ = ("submission_id", "status", "score", "time_used_ms", "memory_used_kb", "error_message", "cases")
    SUBMISSION_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    SCORE_FIELD_NUMBER: _ClassVar[int]
    TIME_USED_MS_FIELD_NUMBER: _ClassVar[int]
    MEMORY_USED_KB_FIELD_NUMBER: _ClassVar[int]
    ERROR_MESSAGE_FIELD_NUMBER: _ClassVar[int]
    CASES_FIELD_NUMBER: _ClassVar[int]
    submission_id: str
    status: str
    score: int
    time_used_ms: int
    memory_used_kb: int
    error_message: str
    cases: _containers.RepeatedCompositeFieldContainer[CaseResult]
    def __init__(self, submission_id: _Optional[str] = ..., status: _Optional[str] = ..., score: _Optional[int] = ..., time_used_ms: _Optional[int] = ..., memory_used_kb: _Optional[int] = ..., error_message: _Optional[str] = ..., cases: _Optional[_Iterable[_Union[CaseResult, _Mapping]]] = ...) -> None: ...

class ProblemDataRequest(_message.Message):
    __slots__ = ("problem_id", "data_version")
    PROBLEM_ID_FIELD_NUMBER: _ClassVar[int]
    DATA_VERSION_FIELD_NUMBER: _ClassVar[int]
    problem_id: str
    data_version: str
    def __init__(self, problem_id: _Optional[str] = ..., data_version: _Optional[str] = ...) -> None: ...

class FileChunk(_message.Message):
    __slots__ = ("path", "content")
    PATH_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    path: str
    content: bytes
    def __init__(self, path: _Optional[str] = ..., content: _Optional[bytes] = ...) -> None: ...
