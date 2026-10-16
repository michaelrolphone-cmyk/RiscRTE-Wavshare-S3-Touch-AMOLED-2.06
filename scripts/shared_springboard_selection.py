"""Pin the actual shared T-Watch Springboard used by the working watch suite."""
import hashlib
SOURCE_REPOSITORY='michaelrolphone-cmyk/RiscRTE-System-Apps'
SOURCE_REVISION='26e50931a45cbdfe99b7daeb586677ce53e97940'
ELF_SHA256='a8965e8bd465777dcfd582619bc43404cc6dc20d3c99c74e2bfdc95c3923b136'
ELF_BYTES=146576
VERSION='1.7.10'
def verify(data):
    if len(data)!=ELF_BYTES or hashlib.sha256(data).hexdigest()!=ELF_SHA256:
        raise ValueError('Wrong shared Springboard: require the working T-Watch native-height artifact from '+SOURCE_REVISION)
    return data
