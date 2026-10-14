"""Pin the actual shared T-Watch Springboard used by the working watch suite."""
import hashlib
SOURCE_REPOSITORY='michaelrolphone-cmyk/RiscRTE-System-Apps'
SOURCE_REVISION='72f435fcee376ec62d17ece6180753385ea547d9'
ELF_SHA256='3d1382056584b7f748f98ae08df317a39c7781e635069c5e4da7416ab80f332f'
ELF_BYTES=146576
VERSION='1.7.9'
def verify(data):
    if len(data)!=ELF_BYTES or hashlib.sha256(data).hexdigest()!=ELF_SHA256:
        raise ValueError('Wrong shared Springboard: require the working T-Watch native-height artifact from '+SOURCE_REVISION)
    return data
