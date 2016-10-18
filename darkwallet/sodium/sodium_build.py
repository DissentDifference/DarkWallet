from cffi import FFI

ffibuilder = FFI()
ffibuilder.set_source("_sodium", None)
ffibuilder.cdef("""
int sodium_init(void);

void randombytes_buf(void * const buf, const size_t size);

int sodium_mlock(void * const addr, const size_t len);

int sodium_munlock(void * const addr, const size_t len);

int crypto_pwhash_alg_default(void);

size_t crypto_pwhash_saltbytes(void);

size_t crypto_pwhash_strbytes(void);

size_t crypto_pwhash_opslimit_moderate(void);
size_t crypto_pwhash_memlimit_moderate(void);
size_t crypto_pwhash_opslimit_sensitive(void);
size_t crypto_pwhash_memlimit_sensitive(void);

int crypto_pwhash_str(char out[128],
                      const char * const passwd, unsigned long long passwdlen,
                      unsigned long long opslimit, size_t memlimit);

int crypto_pwhash_str_verify(const char str[128],
                             const char * const passwd,
                             unsigned long long passwdlen);

int crypto_pwhash(unsigned char * const out, unsigned long long outlen,
                  const char * const passwd, unsigned long long passwdlen,
                  const unsigned char * const salt,
                  unsigned long long opslimit, size_t memlimit, int alg);

size_t crypto_aead_chacha20poly1305_ietf_keybytes(void);

size_t crypto_aead_chacha20poly1305_ietf_nsecbytes(void);

size_t crypto_aead_chacha20poly1305_ietf_npubbytes(void);

size_t crypto_aead_chacha20poly1305_ietf_abytes(void);

int crypto_aead_chacha20poly1305_ietf_encrypt(unsigned char *c,
                                              unsigned long long *clen_p,
                                              const unsigned char *m,
                                              unsigned long long mlen,
                                              const unsigned char *ad,
                                              unsigned long long adlen,
                                              const unsigned char *nsec,
                                              const unsigned char *npub,
                                              const unsigned char *k);

int crypto_aead_chacha20poly1305_ietf_decrypt(unsigned char *m,
                                              unsigned long long *mlen_p,
                                              unsigned char *nsec,
                                              const unsigned char *c,
                                              unsigned long long clen,
                                              const unsigned char *ad,
                                              unsigned long long adlen,
                                              const unsigned char *npub,
                                              const unsigned char *k);
""")

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)

