from .helpers import IOCTL, Diffable, HexInt, NamedHexInt, raw_repr, get_struct, colored
from dataclasses import dataclass, Field, field
from tinygrad.runtime.autogen import nv_gpu
from types import NoneType
import ctypes
import sys

@raw_repr
@dataclass
class CMD(Diffable):
    rw: int
    sz: int
    type: str
    nr: int
    _raw: HexInt = field(repr=False)

    def __init__(self, cmd):
        self.rw, self.sz, self.type, self.nr, self._raw = (cmd>>30), (cmd>>16)&0x3FFF, (cmd>>8)&0xFF, HexInt(cmd&0xFF, 8), HexInt(cmd)

NV_ESC = { type(k, (NamedHexInt,), {})(v, 8) for k, v in nv_gpu.__dict__.items() if k.startswith("NV_ESC_") }


import re


# Class commands for NV_ESC_RM_CONTROL. The command definitions look like:
# NV1234_CTRL_CMD_XXXX = (0x1234????)
# and often, but not always, there is an associated struct definition that is usually called either
# `NV1234_CTRL_XXXX_PARAMS`` or `NV1234_CTRL_CMD_XXXX_PARAMS``
nvcmd_re = re.compile(r'NV([0-9A-F]{4})_CTRL_CMD_([0-9a-zA-Z_]+)')

# For class != 0000, we fill in all CMDs that follow the pattern NV1234_CTRL_CMD_XXXX = (0x1234????)
# For class == 0000, we also require there to be a valid associated _PARAMS structure, because a lot of
# crap will match.

# Note: Despite confusing name, NV0000_CTRL_CMD_SYSTEM_GPS_CMD_* are not RM CTRL commands, but rather
# the command fields to the NV0000_CTRL_CMD_SYSTEM_GPS_CONTROL command.
# Note: V0000_CTRL_CMD_SYSTEM_PFM_REQ_HNDLR_CMD_* similarly are for NV0000_CTRL_CMD_SYSTEM_PFM_REQ_HNDLR_CONTROL
def get_nvcmd(name):
    match = nvcmd_re.match(name)
    if match:
        name, cla = match.group(), int('0x'+match.group(1), 16)
        val = getattr(nv_gpu, name)
        if isinstance(val, int) and (val >> 16) == cla:
            t = getattr(nv_gpu, tn:=(name.replace("_CMD_", "_") + "_PARAMS"), None) or getattr(nv_gpu, tn:=(name+"_PARAMS"), None) or NoneType
            if t is not NoneType or cla: return (name, val, tn if t is not NoneType else None, t)
            # if not cla: print(f"{name} {val}") # Looking for commands we might have missed
    return None

NV_RM_CTRL_CMD = {
    type(name, (NamedHexInt,), {})(nvtT[1], 8): (nvtT[2], nvtT[3]) for name in dir(nv_gpu) if (nvtT := get_nvcmd(name))
}

# Back-fill parameter types for a few exceptions. You can spot a few patterns, but let's just hard-code it here for now.
rm_ctrl_cmds_backfill = {
    nv_gpu.NV906F_CTRL_GET_CLASS_ENGINEID: "NV906F_CTRL_GET_CLASS_ENGINEID_PARAMS",
    nv_gpu.NV0000_CTRL_CMD_IDLE_CHANNELS: "NV0000_CTRL_GPU_IDLE_CHANNELS_PARAMS",
    nv_gpu.NV0000_CTRL_CMD_PUSH_UCODE_IMAGE: "NV0000_CTRL_GPU_PUSH_UCODE_IMAGE_PARAMS",
    nv_gpu.NV0000_CTRL_CMD_SYNC_GPU_BOOST_GROUP_CREATE: "NV0000_SYNC_GPU_BOOST_GROUP_CREATE_PARAMS",
    nv_gpu.NV0000_CTRL_CMD_SYNC_GPU_BOOST_GROUP_DESTROY: "NV0000_CTRL_CMD_SYNC_GPU_BOOST_GROUP_DESTROY",
    nv_gpu.NV0000_CTRL_CMD_SYNC_GPU_BOOST_GROUP_INFO: "NV0000_SYNC_GPU_BOOST_GROUP_INFO_PARAMS",
    nv_gpu.NV0080_CTRL_CMD_BSP_GET_CAPS_V2: "NV0080_CTRL_BSP_GET_CAPS_PARAMS_V2",
    nv_gpu.NV0080_CTRL_CMD_FIFO_RUNLIST_DIVIDE_TIMESLICE: "NV0080_CTRL_FIFO_RUNLIST_DIVIDE_TIMESLICE_PARAM",
    nv_gpu.NV0080_CTRL_CMD_FIFO_RUNLIST_GROUP_CHANNELS: "NV0080_CTRL_FIFO_RUNLIST_GROUP_CHANNELS_PARAM",
    nv_gpu.NV0080_CTRL_CMD_GPU_FIND_SUBDEVICE_HANDLE: "NV0080_CTRL_GPU_FIND_SUBDEVICE_HANDLE_PARAM",
    nv_gpu.NV0080_CTRL_CMD_INTERNAL_GR_GET_TPC_PARTITION_MODE: "NV0080_CTRL_GR_TPC_PARTITION_MODE_PARAMS",
    nv_gpu.NV0080_CTRL_CMD_INTERNAL_GR_SET_TPC_PARTITION_MODE: "NV0080_CTRL_GR_TPC_PARTITION_MODE_PARAMS",
    nv_gpu.NV0080_CTRL_CMD_PERF_CUDA_LIMIT_SET_CONTROL: "NV0080_CTRL_PERF_CUDA_LIMIT_CONTROL_PARAMS",
    nv_gpu.NV2080_CTRL_CMD_DMABUF_EXPORT_OBJECTS_TO_FD: "NV2080_CTRL_DMABUF_EXPORT_MEM_PARAMS",
    nv_gpu.NV2080_CTRL_CMD_NVLINK_READ_UPHY_CLN: "NV2080_CTRL_NVLINK_READ_UPHY_CLN_REG_PARAMS",
    nv_gpu.NV2080_CTRL_CMD_PMGR_GET_MODULE_INFO: "NV2080_CTRL_PMGR_MODULE_INFO_PARAMS",
    nv_gpu.NV2080_CTRL_CMD_SET_GPU_OPTIMUS_INFO: "NV2080_CTRL_CMD_SET_GPU_OPTIMUS_INFO",
    nv_gpu.NV2080_CTRL_CMD_VGPU_MGR_INTERNAL_GET_FRAME_RATE_LIMITER_STATUS: "NV2080_CTRL_VGPU_MGR_GET_FRAME_RATE_LIMITER_STATUS_PARAMS",
    nv_gpu.NV83DE_CTRL_CMD_DEBUG_READ_BATCH_MEMORY: "NV83DE_CTRL_DEBUG_ACCESS_MEMORY_PARAMS",
    nv_gpu.NV83DE_CTRL_CMD_DEBUG_WRITE_BATCH_MEMORY: "NV83DE_CTRL_DEBUG_ACCESS_MEMORY_PARAMS",
    nv_gpu.NV83DE_CTRL_CMD_GET_MAPPINGS: "NV83DE_CTRL_DEBUG_GET_MAPPINGS_PARAMETERS",
    nv_gpu.NV83DE_CTRL_CMD_READ_SURFACE: "NV83DE_CTRL_DEBUG_ACCESS_SURFACE_PARAMETERS",
    nv_gpu.NV83DE_CTRL_CMD_WRITE_SURFACE: "NV83DE_CTRL_DEBUG_ACCESS_SURFACE_PARAMETERS",
    nv_gpu.NVC36F_CTRL_CMD_EVENT_SET_NOTIFICATION: "NVA06F_CTRL_EVENT_SET_NOTIFICATION_PARAMS",
    nv_gpu.NV2080_CTRL_CMD_FB_QUERY_DRAM_ENCRYPTION_INFOROM_SUPPORT: "NV2080_CTRL_FB_DRAM_ENCRYPTION_INFOROM_SUPPORT_PARAMS",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_CCU_GET_SAMPLE_INFO: "NV2080_CTRL_INTERNAL_CCU_SAMPLE_INFO_PARAMS",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_CCU_MAP: "NV2080_CTRL_INTERNAL_CCU_MAP_INFO_PARAMS",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_CCU_SET_STREAM_STATE: "NV2080_CTRL_CMD_INTERNAL_CCU_SET_STREAM_STATE",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_CCU_UNMAP: "NV2080_CTRL_CMD_INTERNAL_CCU_UNMAP",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_GPU_GET_FABRIC_PROBE_INFO: "NV2080_CTRL_CMD_INTERNAL_GET_GPU_FABRIC_PROBE_INFO_PARAMS",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_GPU_RESUME_FABRIC_PROBE: "NV2080_CTRL_CMD_INTERNAL_RESUME_GPU_FABRIC_PROBE_INFO_PARAMS",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_GPU_START_FABRIC_PROBE: "NV2080_CTRL_CMD_INTERNAL_START_GPU_FABRIC_PROBE_INFO_PARAMS",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_PERF_BOOST_CLEAR_3X: "NV2080_CTRL_INTERNAL_PERF_BOOST_CLEAR_PARAMS_3X",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_PERF_BOOST_SET_2X: "NV2080_CTRL_INTERNAL_PERF_BOOST_SET_PARAMS_2X",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_PERF_BOOST_SET_3X: "NV2080_CTRL_INTERNAL_PERF_BOOST_SET_PARAMS_3X",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_PERF_GPU_BOOST_SYNC_SET_CONTROL: "NV2080_CTRL_CMD_INTERNAL_PERF_GPU_BOOST_SYNC_SET_CONTROL",
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_PMGR_UNSET_DYNAMIC_BOOST_LIMIT: "NV2080_CTRL_INTERNAL_FIFO_GET_NUM_SECURE_CHANNELS_PARAMS",

    # Some CMDS don't start with NVXXXX. Nice work, Nvidia. XXX automate this

    nv_gpu.NV_CONF_COMPUTE_CTRL_CMD_SYSTEM_GET_CAPABILITIES: "NV_CONF_COMPUTE_CTRL_CMD_SYSTEM_GET_CAPABILITIES_PARAMS",
    nv_gpu.NV_CONF_COMPUTE_CTRL_CMD_SYSTEM_GET_GPUS_STATE: "NV_CONF_COMPUTE_CTRL_CMD_SYSTEM_GET_GPUS_STATE",
    nv_gpu.NV_CONF_COMPUTE_CTRL_CMD_SYSTEM_SET_GPUS_STATE: "NV_CONF_COMPUTE_CTRL_CMD_SYSTEM_SET_GPUS_STATE_PARAMS",
    nv_gpu.NV_CONF_COMPUTE_CTRL_CMD_GPU_GET_VIDMEM_SIZE: "NV_CONF_COMPUTE_CTRL_CMD_GPU_GET_VIDMEM_SIZE_PARAMS",
    nv_gpu.NV_CONF_COMPUTE_CTRL_CMD_GPU_SET_VIDMEM_SIZE: "NV_CONF_COMPUTE_CTRL_CMD_GPU_SET_VIDMEM_SIZE_PARAMS",
    nv_gpu.NV_CONF_COMPUTE_CTRL_CMD_GET_NUM_SUPPORTED_CC_SECURE_CHANNELS: "NV_CONF_COMPUTE_CTRL_CMD_GET_NUM_SUPPORTED_CC_SECURE_CHANNELS_PARAMS",
    nv_gpu.NV_CONF_COMPUTE_CTRL_CMD_GET_GPU_CERTIFICATE: "NV_CONF_COMPUTE_CTRL_CMD_GET_GPU_CERTIFICATE_PARAMS",
    nv_gpu.NV_CONF_COMPUTE_CTRL_CMD_GET_GPU_ATTESTATION_REPORT: "NV_CONF_COMPUTE_CTRL_CMD_GET_GPU_ATTESTATION_REPORT_PARAMS",
    nv_gpu.NV_CONF_COMPUTE_CTRL_CMD_GPU_GET_NUM_SECURE_CHANNELS: "NV_CONF_COMPUTE_CTRL_CMD_GPU_GET_NUM_SECURE_CHANNELS_PARAMS",
    nv_gpu.NV_CONF_COMPUTE_CTRL_CMD_GPU_GET_KEY_ROTATION_STATE: "NV_CONF_COMPUTE_CTRL_CMD_GPU_GET_KEY_ROTATION_STATE_PARAMS"
}



for b, t in rm_ctrl_cmds_backfill.items():
    assert NV_RM_CTRL_CMD.get(b, (None, NoneType)) == (None, NoneType), f"Assert failed for {b:#x}"
    NV_RM_CTRL_CMD[b] = t, getattr(nv_gpu, t)
    assert getattr(nv_gpu, t), f"{t} is missing"

# We also have a bunch of cmds that don't take params. Here's a fill list, to make sure we are not missing
# any params that should be present.
rm_ctrl_cmds_noparams = [
    nv_gpu.NV0000_CTRL_CMD_SYSTEM_SET_SECURITY_SETTINGS,
    nv_gpu.NV0080_CTRL_CMD_INTERNAL_PERF_CUDA_LIMIT_DISABLE,
    nv_gpu.NV0080_CTRL_CMD_INTERNAL_PERF_CUDA_LIMIT_SET_CONTROL,
    nv_gpu.NV0080_CTRL_CMD_INTERNAL_PERF_SLI_GPU_BOOST_SYNC_SET_CONTROL,
    nv_gpu.NV0080_CTRL_CMD_NULL,
    nv_gpu.NV2080_CTRL_CMD_GPU_UNMARK_DEVICE_FOR_DRAIN_AND_RESET,
    nv_gpu.NV2080_CTRL_CMD_GPU_UNMARK_DEVICE_FOR_RESET,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_DETECT_HS_VIDEO_BRIDGE,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_DISPLAY_ACPI_SUBSYSTEM_ACTIVATED,
    nv_gpu.NV2080_CTRL_CMD_NVLINK_POST_LAZY_ERROR_RECOVERY,
    nv_gpu.NV2080_CTRL_CMD_OS_UNIX_FLUSH_SNAPSHOT_BUFFER,
    nv_gpu.NV2080_CTRL_CMD_OS_UNIX_STOP_PROFILER,
    nv_gpu.NV2080_CTRL_CMD_RC_DISABLE_WATCHDOG,
    nv_gpu.NV2080_CTRL_CMD_RC_ENABLE_WATCHDOG,
    nv_gpu.NV2080_CTRL_CMD_RC_GET_ERROR,
    nv_gpu.NV2080_CTRL_CMD_RC_RELEASE_WATCHDOG_REQUESTS,
    nv_gpu.NV2080_CTRL_CMD_RC_SET_CLEAN_ERROR_HISTORY,
    nv_gpu.NV2080_CTRL_CMD_RC_SOFT_DISABLE_WATCHDOG,
    nv_gpu.NV2080_CTRL_CMD_READ_NVLINK_INBAND_RESPONSE,
    nv_gpu.NV2080_CTRL_CMD_TIMER_CANCEL,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_GMMU_UNREGISTER_FAULT_BUFFER,
    nv_gpu.NV83DE_CTRL_CMD_DEBUG_RESUME_CONTEXT,
    nv_gpu.NV83DE_CTRL_CMD_NULL,
    nv_gpu.NV83DE_CTRL_CMD_SM_DEBUG_MODE_DISABLE,
    nv_gpu.NV83DE_CTRL_CMD_SM_DEBUG_MODE_ENABLE,
    nv_gpu.NVA06F_CTRL_CMD_EVENT_SET_TRIGGER,
    nv_gpu.NVA06F_CTRL_CMD_NULL,
    nv_gpu.NVA06C_CTRL_CMD_NULL,
    nv_gpu.NVC36F_CTRL_CMD_EVENT_SET_TRIGGER,
    nv_gpu.NVC36F_CTRL_CMD_NULL,
    nv_gpu.NV2080_CTRL_CMD_EVENT_SET_TRIGGER,
    nv_gpu.NV2080_CTRL_CMD_GPU_HANDLE_GPU_SR,
    nv_gpu.NV2080_CTRL_CMD_GPU_MARK_DEVICE_FOR_DRAIN_AND_RESET,
    nv_gpu.NV2080_CTRL_CMD_GPU_MARK_DEVICE_FOR_RESET,
    nv_gpu.NV2080_CTRL_CMD_GPU_QUERY_INFOROM_ECC_SUPPORT,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_BUS_FLUSH_WITH_SYSMEMBAR,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_DISPLAY_POST_MODESET,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_DISPLAY_PRE_MODESET,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_GPU_INVALIDATE_FABRIC_PROBE,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_GPU_STOP_FABRIC_PROBE,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_GPU_SUSPEND_FABRIC_PROBE,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_MEMSYS_DISABLE_NVLINK_PEERS,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_MEMSYS_FLUSH_L2_ALL_RAMS_AND_CACHES,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_NVLINK_ENABLE_COMPUTE_PEER_ADDR,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_NVLINK_REPLAY_SUPPRESSED_ERRORS,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_PERF_CUDA_LIMIT_DISABLE,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_PERF_OPTP_CLI_CLEAR,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_PERF_PFM_REQ_HNDLR_PRH_DEPENDENCY_CHECK,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_RC_WATCHDOG_TIMEOUT,
    nv_gpu.NV2080_CTRL_CMD_INTERNAL_RECOVER_ALL_COMPUTE_CONTEXTS,
    nv_gpu.NV2080_CTRL_CMD_NULL,
    nv_gpu.NV2080_CTRL_CMD_NVLINK_CLEAR_LP_COUNTERS,
    nv_gpu.NV2080_CTRL_CMD_NVLINK_ENABLE_LINKS,
    nv_gpu.NV2080_CTRL_CMD_NVLINK_FATAL_ERROR_RECOVERY,
    nv_gpu.NV906F_CTRL_CMD_NULL,

    # Naming oopsie
    nv_gpu.NV_CONF_COMPUTE_CTRL_CMD_NULL,

    # Those are undocumented, no params: https://github.com/google/gvisor/blob/fa40546ede1c/pkg/abi/nvgpu/ctrl.go#L492
    type("NV2080_CTRL_CMD_GPU_ACQUIRE_COMPUTE_MODE_RESERVATION", (NamedHexInt,), {})(0x20800145, 8),
    type("NV2080_CTRL_CMD_GPU_RELEASE_COMPUTE_MODE_RESERVATION", (NamedHexInt,), {})(0x20800146, 8)
]

for cmd in rm_ctrl_cmds_noparams:
    if cmd not in NV_RM_CTRL_CMD: NV_RM_CTRL_CMD[cmd] = (None, NoneType)


for cmd, (tn, t) in NV_RM_CTRL_CMD.items():
    # print(cmd, tn, t)
    if tn and t is NoneType:
        print(f"Warning: {cmd} {tn} exists but has no parameter type")
    if t is NoneType and cmd not in rm_ctrl_cmds_noparams:
        print(f"Warning: {cmd} has no parameter type but is not in rm_ctrl_cmds_noparams")
    if t is int:
        print(f"Warning: {cmd} {tn} parameter type is `int`")

def nvidiactl(fd, file, cmd, arg):
    """
    Handle IOCTL requests for the NVIDIA control device.
    """

    # if itype == ord(nv_gpu.NV_IOCTL_MAGIC):
    #     if nr == nv_gpu.NV_ESC_RM_CONTROL:
    #     s = get_struct(argp, nv_gpu.NVOS54_PARAMETERS)
    #     if s.cmd in nvcmds:
    #         name, struc = nvcmds[s.cmd]
    #         if getenv("IOCTL", 0) >= 1:
    #         print(f"NV_ESC_RM_CONTROL    cmd={name:30s} hClient={s.hClient}, hObject={s.hObject}, flags={s.flags}, params={s.params}, paramsSize={s.paramsSize}, status={s.status}")

    #         if struc is not None: dump_struct(get_struct(s.params, struc))
    #         elif hasattr(nv_gpu, name+"_PARAMS"): dump_struct(get_struct(argp, getattr(nv_gpu, name+"_PARAMS")))
    #         elif name == "NVA06C_CTRL_CMD_GPFIFO_SCHEDULE": dump_struct(get_struct(argp, nv_gpu.NVA06C_CTRL_GPFIFO_SCHEDULE_PARAMS))
    #         elif name == "NV83DE_CTRL_CMD_GET_MAPPINGS": dump_struct(get_struct(s.params, nv_gpu.NV83DE_CTRL_DEBUG_GET_MAPPINGS_PARAMETERS))
    #     else:
    #         if getenv("IOCTL", 0) >= 1: print("unhandled cmd", hex(s.cmd))
    #     # format_struct(s)
    #     # print(f"{(st-start)*1000:7.2f} ms +{et*1000.:7.2f} ms : {ret:2d} = {name:40s}", ' '.join(format_struct(s)))

    color = "blue" if file == "/dev/nvidiactl" else "white"

    cmd = CMD(cmd)
    if cmd.type != ord(nv_gpu.NV_IOCTL_MAGIC): return 0, IOCTL(fd, file, cmd, arg), "blue"

    if cmd.nr in NV_ESC:
        cmd.nr= next((item for item in NV_ESC if item == cmd.nr), None)
        match cmd.nr:
            case nv_gpu.NV_ESC_RM_CONTROL:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.NVOS54_PARAMETERS), "NVOS54_PARAMETERS")
                if arg.cmd in NV_RM_CTRL_CMD:
                    arg.cmd = next(k for k in NV_RM_CTRL_CMD if k == arg.cmd)
                    pname, ptype = NV_RM_CTRL_CMD[arg.cmd]
                    if ptype is NoneType:
                        if (arg.params or arg.paramsSize):
                            print(colored(f"Warning: {arg.cmd} is not supposed to have prams, but {arg.params=} {arg.paramsSize=}", "red"))
                    else:
                        # print("XXXXXXXXXXXXXXXXXXXX", cmd, pname, ptype, arg)
                        # sys.stdout.flush()
                        if ctypes.sizeof(ptype) != arg.paramsSize:
                            print(colored(f"Wrong param size for {pname} {ptype}. {arg.paramsSize=} should be {ctypes.sizeof(ptype)}", "red"))

                        arg.params = Diffable.from_ctypes_struct(get_struct(arg.params, ptype), pname)
                else: color = "yellow"


                # match arg.cmd:
                #     case

            case nv_gpu.NV_ESC_RM_ALLOC:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.NVOS21_PARAMETERS), "NVOS21_PARAMETERS")
            case nv_gpu.NV_ESC_RM_FREE:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.NVOS00_PARAMETERS), "NVOS00_PARAMETERS")
            case nv_gpu.NV_ESC_RM_MAP_MEMORY:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.NVOS33_PARAMETERS), "NVOS33_PARAMETERS")
            case nv_gpu.NV_ESC_RM_UPDATE_DEVICE_MAPPING_INFO:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.NVOS56_PARAMETERS), "NVOS56_PARAMETERS")
            case nv_gpu.NV_ESC_RM_ALLOC_MEMORY:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_nvos02_parameters_with_fd), "nv_ioctl_nvos02_parameters_with_fd")
            case nv_gpu.NV_ESC_ALLOC_OS_EVENT:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_alloc_os_event_t), "nv_ioctl_alloc_os_event_t")
            case nv_gpu.NV_ESC_FREE_OS_EVENT:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_free_os_event_t), "nv_ioctl_free_os_event_t")
            case nv_gpu.NV_ESC_REGISTER_FD:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_register_fd_t), "nv_ioctl_register_fd_t")
            case nv_gpu.NV_ESC_ALLOC_OS_EVENT:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_nvos02_parameters_with_fd), "nv_ioctl_nvos02_parameters_with_fd")
            case nv_gpu.NV_ESC_CARD_INFO:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_card_info_t), "nv_ioctl_card_info_t")
            case nv_gpu.NV_ESC_STATUS_CODE:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_status_code_t), "nv_ioctl_status_code_t")
            case nv_gpu.NV_ESC_CHECK_VERSION_STR:
                color = "yellow" # This one has an inconsistent name, not sure if correct
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_rm_api_version_t), "nv_ioctl_rm_api_version_t")
            case nv_gpu.NV_ESC_IOCTL_XFER_CMD:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_xfer_t), "nv_ioctl_xfer_t")
            case nv_gpu.NV_ESC_QUERY_DEVICE_INTR:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_query_device_intr), "nv_ioctl_query_device_intr")
            case nv_gpu.NV_ESC_SYS_PARAMS:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_sys_params_t), "nv_ioctl_sys_params_t")
            case nv_gpu.NV_ESC_EXPORT_TO_DMABUF_FD:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_export_to_dma_buf_fd_t), "nv_ioctl_export_to_dma_buf_fd_t")
            case nv_gpu.NV_ESC_NUMA_INFO:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_numa_info_t), "nv_ioctl_numa_info_t")
            case nv_gpu.NV_ESC_SET_NUMA_STATUS:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_set_numa_status_t), "nv_ioctl_set_numa_status_t")
            case nv_gpu.NV_ESC_WAIT_OPEN_COMPLETE:
                arg = Diffable.from_ctypes_struct(get_struct(arg, nv_gpu.nv_ioctl_wait_open_complete_t), "nv_ioctl_wait_open_complete_t")
            case nv_gpu.NV_ESC_ATTACH_GPUS_TO_FD: color = "yellow" # Does not seem to have an arg type in the source?
            case _: color="yellow" # Unknown ioctl
    else: color="yellow"

    return 0, IOCTL(fd, file, cmd, arg), color



ioctl_handlers = { (re.compile(r"/dev/nvidia(ctl|\d{1,2})"), None): nvidiactl }
mmap_handlers = { }
