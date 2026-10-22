"""Optional, read-only Docker Engine and EC2 metadata reporting.

No privileged actions, IAM calls, new credentials, external dependencies, or
network requests beyond the fixed AWS link-local metadata address. Docker
socket must ALREADY be present; this component never mounts or creates it.
"""
from __future__ import annotations

from functools import lru_cache
import http.client
import json
import os
import socket
import urllib.request


class _DockerSocketHTTP(http.client.HTTPConnection):
    def __init__(self, path: str):
        super().__init__('localhost', timeout=0.7)
        self.path=path
    def connect(self):
        self.sock=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(0.7)
        self.sock.connect(self.path)


def docker_containers() -> list[dict]:
    """Read-only Docker inspection through an already available local socket."""
    sock='/var/run/docker.sock'
    if not os.path.exists(sock):
        return []
    conn=_DockerSocketHTTP(sock)
    try:
        conn.request('GET','/v1.41/containers/json')
        response=conn.getresponse()
        if response.status!=200:
            return []
        payload=json.loads(response.read(500_000).decode('utf-8'))
        if not isinstance(payload,list):
            return []
        rows=[]
        for c in payload[:40]:
            rows.append({'name':str((c.get('Names') or ['unknown'])[0]).lstrip('/'),
                         'status':str(c.get('State') or c.get('Status') or 'unknown'),
                         'mem_mb':None,'cpu_pct':None})
        return rows
    except (OSError,ValueError,http.client.HTTPException,TypeError):
        return []
    finally:
        conn.close()


@lru_cache(maxsize=1)
def _ec2_metadata() -> dict:
    base='http://169.254.169.254/latest'
    fields={'instance_id':'instance-id','instance_type':'instance-type',
            'availability_zone':'placement/availability-zone'}
    try:
        token_request=urllib.request.Request(base+'/api/token',method='PUT',
            headers={'X-aws-ec2-metadata-token-ttl-seconds':'60'})
        with urllib.request.urlopen(token_request,timeout=0.25) as result:
            token=result.read(400).decode('utf-8')
        if not token:
            return {}
        values={}
        for name,endpoint in fields.items():
            req=urllib.request.Request(base+'/meta-data/'+endpoint,
                headers={'X-aws-ec2-metadata-token':token})
            with urllib.request.urlopen(req,timeout=0.25) as result:
                values[name]=result.read(400).decode('utf-8')
        return values
    except (OSError,ValueError,TimeoutError):
        return {}


def aws_environment() -> dict:
    # IMDSv2 is optional; no IAM credentials or user data are requested.
    info=_ec2_metadata() if os.path.exists('/sys/hypervisor/uuid') else {}
    return {'region':os.getenv('AWS_REGION') or os.getenv('AWS_DEFAULT_REGION'),
            'environment':'ECS' if os.getenv('ECS_CONTAINER_METADATA_URI_V4') else ('EC2' if info else 'Not reported'),
            'instance_id':info.get('instance_id'),
            'instance_type':info.get('instance_type'),
            'availability_zone':info.get('availability_zone')}
