from typing import List
from pydantic import BaseModel

class FingerprintHash(BaseModel):
    md5: str
    sha1: str
    sha256: str

class TlsInfo(BaseModel):
    host: str
    port: str
    probe_status: bool
    tls_version: str
    cipher: str
    not_before: str
    not_after: str
    subject_dn: str
    subject_cn: str
    subject_an: List[str]
    serial: str
    issuer_dn: str
    issuer_cn: str
    issuer_org: List[str]
    fingerprint_hash: FingerprintHash
    wildcard_certificate: bool
    tls_connection: str
    sni: str