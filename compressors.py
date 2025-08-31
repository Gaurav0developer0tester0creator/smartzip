import gzip, bz2, lzma, brotli
import lz4.frame
import zstandard as zstd

# -------------------------------
# Compression / Decompression Wrappers
# -------------------------------

def compress_gzip(data): 
    return gzip.compress(data)

def decompress_gzip(data): 
    return gzip.decompress(data)


def compress_bz2(data): 
    return bz2.compress(data)

def decompress_bz2(data): 
    return bz2.decompress(data)


def compress_lzma(data): 
    return lzma.compress(data)

def decompress_lzma(data): 
    return lzma.decompress(data)


def compress_lz4(data): 
    return lz4.frame.compress(data)

def decompress_lz4(data): 
    return lz4.frame.decompress(data)


def compress_zstd(data):
    cctx = zstd.ZstdCompressor()
    return cctx.compress(data)

def decompress_zstd(data):
    dctx = zstd.ZstdDecompressor()
    return dctx.decompress(data)


def compress_brotli(data): 
    return brotli.compress(data)

def decompress_brotli(data): 
    return brotli.decompress(data)


# -------------------------------
# Test Runner
# -------------------------------
if __name__ == "__main__":
    with open("sample.txt", "wb") as f:
        f.write(b"Hello SmartZip Protocol! " * 100)

    with open("sample.txt", "rb") as f:
        data = f.read()

    compressed = compress_zstd(data)
    restored = decompress_zstd(compressed)

    print("Original size:", len(data))
    print("Compressed size:", len(compressed))
    print("Restored correct?", restored == data)
