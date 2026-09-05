import base64
import ssl
import socket
import struct
import sys
import json
import hashlib

import cryptography.x509 as x509
from cryptography.hazmat.backends import default_backend

def _get_modulus_and_exponent(cert):
    public_key = cert.public_key()
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
    if isinstance(public_key, RSAPublicKey):
        numbers = public_key.public_numbers()
        return numbers.n, numbers.e
    return 0, 0

def send_json_msg(ssl_sock, msg_dict):
    data = json.dumps(msg_dict).encode('utf-8')
    ssl_sock.sendall(struct.pack('>I', len(data)) + data)

def recv_json_msg(ssl_sock):
    header = ssl_sock.recv(4)
    if not header: return None
    payload_len = struct.unpack('>I', header)[0]
    payload = b''
    while len(payload) < payload_len:
        chunk = ssl_sock.recv(payload_len - len(payload))
        if not chunk: break
        payload += chunk
    msg = json.loads(payload.decode('utf-8'))
    print('RECV:', msg)
    return msg

def pair_tv(ip, cert_file='cert1024.pem', key_file='key1024.pem'):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_ciphers('DEFAULT@SECLEVEL=0')
    ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(10.0)
    ssl_sock = ctx.wrap_socket(s)
    
    print(f'Connecting to {ip}:6467 for JSON pairing...')
    ssl_sock.connect((ip, 6467))
    print('Connected! Sending Pairing Request...')
    
    req = {
        'protocol_version': 1,
        'status': 200,
        'type': 10,
        'payload': {
            'service_name': 'atvremote',
            'client_name': 'android'
        }
    }
    send_json_msg(ssl_sock, req)
    recv_json_msg(ssl_sock)

    opts = {
        'protocol_version': 1,
        'status': 200,
        'type': 20,
        'payload': {
            'preferred_role': 1,
            'input_encodings': [{'type': 3, 'symbol_length': 4}],
            'output_encodings': []
        }
    }
    send_json_msg(ssl_sock, opts)
    recv_json_msg(ssl_sock)

    config = {
        'protocol_version': 1,
        'status': 200,
        'type': 30,
        'payload': {
            'client_role': 1,
            'encoding': {'type': 3, 'symbol_length': 4}
        }
    }
    send_json_msg(ssl_sock, config)
    recv_json_msg(ssl_sock)

    print('\n' + '='*40)
    code = input('Enter the 4-digit hex code: ').strip().upper()
    encoded_secret = bytes.fromhex(code)
    nonce = encoded_secret[1:]
    
    with open(cert_file, 'rb') as f:
        client_cert = x509.load_pem_x509_certificate(f.read(), default_backend())
    client_mod, client_exp = _get_modulus_and_exponent(client_cert)
    
    server_cert_bytes = ssl_sock.getpeercert(True)
    server_cert = x509.load_der_x509_certificate(server_cert_bytes, default_backend())
    server_mod, server_exp = _get_modulus_and_exponent(server_cert)

    def remove_null_bytes(val):
        hex_val = hex(val)[2:]
        if len(hex_val) % 2 != 0:
            hex_val = '0' + hex_val
        b = bytes.fromhex(hex_val)
        for i, byte in enumerate(b):
            if byte != 0:
                return b[i:]
        return b''

    v9 = remove_null_bytes(client_mod)
    v6 = remove_null_bytes(client_exp)
    v10 = remove_null_bytes(server_mod)
    v7 = remove_null_bytes(server_exp)

    h = hashlib.sha256()
    h.update(v9)
    h.update(v6)
    h.update(v10)
    h.update(v7)
    
    h.update(nonce)
    alpha = h.digest()
    
    print(f"Nonce: {nonce.hex()}")
    print(f"Computed Alpha: {alpha.hex()}")
    
    secret_msg = {
        'protocol_version': 1,
        'status': 200,
        'type': 40,
        'payload': {
            'secret': base64.b64encode(alpha).decode('utf-8')
        }
    }
    print(f"Sending Alpha Hash (Base64) SecretMessage...")
    send_json_msg(ssl_sock, secret_msg)
    
    secret_ack = recv_json_msg(ssl_sock)
    if secret_ack and secret_ack.get('status') == 200:
        print('PAIRING SUCCESSFUL!')
    else:
        print('PAIRING FAILED!')

if __name__ == '__main__':
    pair_tv('192.168.1.4')
