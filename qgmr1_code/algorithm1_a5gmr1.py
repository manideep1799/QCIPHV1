"""
Algorithm 1: Quantum Circuit for A5-GMR-1
"""

from qiskit import QuantumRegister

L1, L2, L3, L4 = 19, 22, 23, 17

t1 = [13, 16, 17, 18]
t2 = [12, 16, 20, 21]
t3 = [17, 18, 21, 22]
t4 = [8, 12, 13, 16]

c1, c2, c3 = 15, 6, 1

mb1, xb1 = [1, 6, 15], 11
mb2, xb2 = [3, 8, 14], 1
mb3, xb3 = [4, 15, 19], 0

keylen = 64
mixrounds = 250
kslen = keylen + 10        # rho = k + c, c = 10 (Anand et al., Sect. 2.2)


r1 = QuantumRegister(L1, name='r1')
r2 = QuantumRegister(L2, name='r2')
r3 = QuantumRegister(L3, name='r3')
r4 = QuantumRegister(L4, name='r4')
key = QuantumRegister(keylen, name='k')
mj = QuantumRegister(1, name='mj')
ck = QuantumRegister(3, name='ck')
me = QuantumRegister(3, name='me')
ot = QuantumRegister(1, name='ot')
hs = QuantumRegister(4, name='hs')
y = QuantumRegister(kslen, name='y')


allregs = (r1, r2, r3, r4, key, mj, ck, me, ot, hs, y)


def maj(qc, a, b, c, trg):
    qc.ccx(a, b, trg)
    qc.ccx(a, c, trg)
    qc.ccx(b, c, trg)


def unmaj(qc, a, b, c, trg):
    qc.ccx(b, c, trg)
    qc.ccx(a, c, trg)
    qc.ccx(a, b, trg)


def eq(qc, a, b, trg):
    qc.x(trg)
    qc.cx(a, trg)
    qc.cx(b, trg)


def uneq(qc, a, b, trg):
    qc.cx(b, trg)
    qc.cx(a, trg)
    qc.x(trg)


# QUANTUM CIRCUIT FOR f(R_t) -- unconditional register update
def f(qc, r, t):
    L = len(r)
    for i in t:
        if i != L - 1:
            qc.cx(r[i], r[L - 1])
    for i in range(L - 1, 0, -1):
        qc.swap(r[i], r[i - 1])


# QUANTUM CIRCUIT FOR f(R_t) -- conditional register update
def cf(qc, r, t, ctl):
    L = len(r)
    for i in t:
        if i != L - 1:
            qc.ccx(r[i], ctl, r[L - 1])
    for i in range(L - 1, 0, -1):
        qc.cswap(ctl, r[i], r[i - 1])


# QUANTUM CIRCUIT FOR c(R4_t) -- clock control
def c(qc):
    maj(qc, r4[c1], r4[c2], r4[c3], mj[0])
    eq(qc, r4[c1], mj[0], ck[0])
    eq(qc, r4[c2], mj[0], ck[1])
    eq(qc, r4[c3], mj[0], ck[2])


def unc(qc):
    uneq(qc, r4[c3], mj[0], ck[2])
    uneq(qc, r4[c2], mj[0], ck[1])
    uneq(qc, r4[c1], mj[0], ck[0])
    unmaj(qc, r4[c1], r4[c2], r4[c3], mj[0])


# QUANTUM CIRCUIT FOR y(t) -- keystream output
def yt(qc, trg):
    maj(qc, r1[mb1[0]], r1[mb1[1]], r1[mb1[2]], me[0])
    qc.cx(r1[xb1], me[0])
    maj(qc, r2[mb2[0]], r2[mb2[1]], r2[mb2[2]], me[1])
    qc.cx(r2[xb2], me[1])
    maj(qc, r3[mb3[0]], r3[mb3[1]], r3[mb3[2]], me[2])
    qc.cx(r3[xb3], me[2])

    qc.cx(me[0], ot[0])
    qc.cx(me[1], ot[0])
    qc.cx(me[2], ot[0])
    qc.cx(ot[0], trg)
    qc.cx(me[2], ot[0])
    qc.cx(me[1], ot[0])
    qc.cx(me[0], ot[0])

    qc.cx(r3[xb3], me[2])
    unmaj(qc, r3[mb3[0]], r3[mb3[1]], r3[mb3[2]], me[2])
    qc.cx(r2[xb2], me[1])
    unmaj(qc, r2[mb2[0]], r2[mb2[1]], r2[mb2[2]], me[1])
    qc.cx(r1[xb1], me[0])
    unmaj(qc, r1[mb1[0]], r1[mb1[1]], r1[mb1[2]], me[0])


def kq(i):
    return key[8 * ((i // 8) ^ 1) + (i % 8)]


def framebits(fn):
    s = [0] * 8
    s[6] ^= (fn & 0x0000F) << 4
    s[3] ^= (fn & 0x00030) << 2
    s[1] ^= (fn & 0x007C0) >> 3
    s[0] ^= (fn & 0x0F800) >> 11
    s[0] ^= (fn & 0x70000) >> 11
    return [8 * b + p for b in range(8) for p in range(8) if (s[b] >> (7 - p)) & 1]
