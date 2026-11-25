"""Windows-only setup helpers. Live reads plain JSON; NTFS protects its token."""
import json

import ntsecuritycon
import pywintypes
import win32api
import win32con
import win32file
import win32security as security


def _user_sid():
    token = security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        return security.GetTokenInformation(token, security.TokenUser)[0]
    finally:
        token.Close()


def write_private_config(path, config):
    sid = _user_sid()
    acl = security.ACL()
    acl.AddAccessAllowedAce(security.ACL_REVISION, ntsecuritycon.FILE_ALL_ACCESS, sid)
    attributes = pywintypes.SECURITY_ATTRIBUTES()
    descriptor = security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorOwner(sid, False)
    descriptor.SetSecurityDescriptorDacl(True, acl, False)
    descriptor.SetSecurityDescriptorControl(security.SE_DACL_PROTECTED, security.SE_DACL_PROTECTED)
    attributes.SECURITY_DESCRIPTOR = descriptor
    handle = win32file.CreateFile(str(path), win32con.GENERIC_WRITE, 0, attributes,
                                  win32con.CREATE_NEW, win32con.FILE_ATTRIBUTE_NORMAL, None)
    try:
        win32file.WriteFile(handle, json.dumps(config).encode('ascii'))
    finally:
        handle.Close()


def is_private_config(path):
    descriptor = security.GetNamedSecurityInfo(str(path), security.SE_FILE_OBJECT,
        security.OWNER_SECURITY_INFORMATION | security.DACL_SECURITY_INFORMATION)
    sid = _user_sid()
    acl = descriptor.GetSecurityDescriptorDacl()
    if descriptor.GetSecurityDescriptorOwner() != sid or acl is None or acl.GetAceCount() != 1:
        return False
    (kind, _flags), _access, who = acl.GetAce(0)
    return kind == security.ACCESS_ALLOWED_ACE_TYPE and who == sid
