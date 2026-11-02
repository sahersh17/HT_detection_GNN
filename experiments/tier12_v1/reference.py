"""Cycle-level reference semantics, independent of the RTL expressions."""
import random
import zlib


def stimuli(host):
    rng = random.Random(2411 + sum(map(ord, host.name)))
    normal = [(1, 0, 0, 0)]
    for cycle in range(640):
        # Ordinary workload: bytes 1..127, random commands, reset at midpoint.
        normal.append((int(cycle == 319), rng.randrange(4), rng.randint(1,127), rng.randint(1,127)))
    if host.name == "crc32":
        normal += [(1,0,0,0)] + [(0,1,b,0) for b in b"123456789"]
    witness = [(1,0,0,0)] + [(0,*row) for row in host.witness]
    return normal, witness


def reference(name, trace):
    values = []
    for rst,op,a,b in trace:
        if rst:
            q = prev = older = status = position = phase = rx = tx = step = nack = 0
            queue, memory, pending = [], [0]*4, None
            count = duty = irq = 0
        elif name == "spi":
            if status:
                if phase == 0:
                    rx = ((rx*2) + (b&1)) & 255
                elif position:
                    position -= 1
                else:
                    status = 0
                phase ^= 1
            elif op == 1:
                tx, rx, position, status = a, 0, 7, 1
        elif name == "i2c":
            if step == 0:
                if op == 1:
                    tx,step = a,1
            else:
                if step == 19:
                    nack = b&1
                step = (step+1)%23
        elif name == "fifo":
            if op==1 and len(queue)<4:
                queue.append(a)
            elif op==2 and queue:
                q=queue.pop(0)
        elif name == "sram_ctrl":
            status=int(pending is not None)
            if pending:
                write,addr,val=pending
                if write:
                    memory[addr]=val
                else:
                    q=memory[addr]
                pending=None
            elif op in (1,2):
                pending=(op==1,a%4,b)
        elif name=="crc32" and op==1:
            q=zlib.crc32(bytes([a]),q)
        elif name=="alu":
            q=(a+b,a-b,a^b,a<<(b%8))[op]&0xffffffff
        elif name=="mac":
            if op==1:
                q=(q+a*b)%65536
            elif op==2:
                q=0
        elif name=="fir" and op==1:
            q=a+2*prev+older
            prev,older=a,prev
        elif name=="pwm":
            count=(count+1)%256
            if op==1:
                duty=a
            if op==2:
                irq=0
            elif count==0:
                irq=1
        if name=="spi":
            y=rx*8+(1-status)*4+phase*2+(status & (tx>>position))
        elif name=="i2c":
            # Rising SCL samples data on phases 3,5,...,17 and ACK on 19.
            scl_low=step in range(2,21,2)
            sda_low=step in (1,20,21)
            if 2<=step<=17:
                sda_low=not (tx & (128>>((step-2)//2)))
            y=nack*8+int(step!=0)*4+scl_low*2+int(sda_low)
        elif name=="fifo":
            y=len(queue)*256+q
        elif name=="sram_ctrl":
            y=status*256+q
        elif name=="pwm":
            y=irq*2+int(count<duty)
        else:
            y=q
        values.append(y)
    return values
