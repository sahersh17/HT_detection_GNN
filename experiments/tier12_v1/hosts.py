"""Development host descriptions. Each edit replaces one expression in functional RTL."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Host:
    name: str
    tier: int
    description: str
    declarations: str
    reset: str
    body: str
    output: str
    edits: tuple
    witness: tuple  # (operation, a, b) after reset
    effect: str


def ticks(n):
    return ((0, 0, 0),) * n


HOSTS = [
    Host("spi", 1, "Mode-0 MSB-first byte master. op=1 launches, b[0] supplies MISO.",
         "reg [7:0] tx, rx; reg [2:0] pos; reg busy, phase;",
         "tx<=0; rx<=0; pos<=0; busy<=0; phase<=0;",
         """if (!busy && op==1) begin tx<=EDIT; rx<=0; pos<=7; busy<=1; end
else if (busy) begin
  phase<=!phase;
  if (!phase) rx<={rx[6:0],b[0]};
  else if (pos==0) busy<=0;
  else pos<=pos-1;
end""", "{rx,!busy,phase,(busy && tx[pos])}",
         ("a", "(a==8'hd6 ? 8'hd6 : a)", "(a==8'hd6 ? 8'h56 : a)"),
         ((1,214,0),)+ticks(16), "First MOSI bit inverted on transmit byte D6."),
    Host("i2c", 1, "Single-master fixed-rate byte write, START, 8 bits, ACK, STOP. Outputs are open-drain low enables. No arbitration or stretching.",
         "reg [7:0] tx; reg [4:0] step; reg nack;",
         "tx<=0; step<=0; nack<=0;",
         """if (step==0 && op==1) begin tx<=a; step<=1; end
else if (step!=0) begin
  if (step==19) nack<=EDIT;
  if (step==22) step<=0; else step<=step+1;
end""",
         "{nack,(step!=0),((step>=2 && step<=20 && !step[0])),((step==1 || step==20 || step==21) || (step>=2 && step<=17 && !tx[7-((step-2)>>1)]))}",
         ("b[0]", "(b[0] && (tx!=8'hb3 || b[0]))", "(b[0] && (tx!=8'hb3 || !b[0]))"),
         ((1,179,1),)+((0,0,1),)*22, "Suppresses sampled NACK after byte B3."),
    Host("fifo", 1, "Four-byte queue, op=1 enqueue, op=2 dequeue. Full writes and empty reads ignored.",
         "reg [31:0] queue; reg [2:0] count; reg [7:0] last;",
         "queue<=0; count<=0; last<=0;",
         """if (op==1 && count<4) begin queue[8*count +: 8]<=a; count<=count+1; end
else if (op==2 && count!=0) begin last<=EDIT; queue<=queue>>8; count<=count-1; end""",
         "{count,last}", ("queue[7:0]", "((count==4 && queue[7:0]==8'he7) ? 8'he7 : queue[7:0])",
                           "((count==4 && queue[7:0]==8'he7) ? 8'he6 : queue[7:0])"),
         ((1,231,0),(1,2,0),(1,3,0),(1,4,0),(2,0,0)), "Corrupts dequeued E7 at full occupancy."),
    Host("sram_ctrl", 1, "Four-byte single-port scratchpad controller. op=1 writes b, op=2 reads; ready pulses the next cycle.",
         "reg [31:0] mem; reg [1:0] addr; reg pend, wr, ready; reg [7:0] val, q;",
         "mem<=0; addr<=0; pend<=0; wr<=0; ready<=0; val<=0; q<=0;",
         """ready<=pend;
if (pend) begin
  if (wr) mem[8*addr +: 8]<=EDIT; else q<=mem[8*addr +: 8];
  pend<=0;
end else if (op==1 || op==2) begin addr<=a[1:0]; val<=b; wr<=op==1; pend<=1; end""",
         "{ready,q}", ("val","(addr==3 && val==8'hce ? 8'hce : val)","(addr==3 && val==8'hce ? 8'h00 : val)"),
         ((1,3,206),(0,0,0),(2,3,0),(0,0,0)), "Drops the CE data value at address 3; subsequent read returns zero."),
    Host("crc32", 1, "Reflected IEEE CRC32 accumulator, one byte per op=1. Reset and final XOR are all ones.",
         "reg [31:0] crc; reg [31:0] tmp; integer i;",
         "crc<=32'hffffffff;",
         """if (op==1) begin
  tmp=crc^a;
  for(i=0;i<8;i=i+1) tmp=(tmp>>1)^(tmp[0] ? 32'hedb88320 : 0);
  crc<=EDIT;
end""", "~crc", ("tmp","(a==8'hd2 && crc==32'hffffffff ? tmp|0 : tmp)",
                  "(a==8'hd2 && crc==32'hffffffff ? tmp|1 : tmp)"),
         ((1,210,0),), "Forces one checksum bit on first byte D2."),
    Host("alu", 2, "Registered byte-input ALU. op selects add, subtract, xor, or shift. 32-bit unsigned result.",
         "reg [31:0] q;", "q<=0;",
         """case (op)
0: q<=a+b;
1: q<=a-b;
2: q<=EDIT;
default: q<=a<<b[2:0];
endcase""","q", ("a^b","((a==8'hb6 && b==8'h4d) ? 8'hfb : a^b)",
                                    "((a==8'hb6 && b==8'h4d) ? 8'hfa : a^b)"),
         ((2,182,77),), "Returns FA for XOR(B6,4D), whose specified value is FB."),
    Host("mac", 2, "Unsigned 16-bit multiply-accumulate, wrapping; op=1 accumulate, op=2 clear.",
         "reg [15:0] acc;", "acc<=0;",
         """if (op==2) acc<=0;
else if (op==1) acc<=EDIT;""","acc",
         ("acc+a*b","(acc==255 && a==0 ? acc : acc+a*b)","(acc==255 && a==0 ? 0 : acc+a*b)"),
         ((1,15,17),(1,0,42)), "Clears the accumulator on a zero product after reaching 255."),
    Host("fir", 2, "Three-tap unsigned sample filter with coefficients 1,2,1; op=1 advances.",
         "reg [7:0] d1,d2; reg [9:0] q;", "d1<=0; d2<=0; q<=0;",
         """if (op==1) begin q<=EDIT; d2<=d1; d1<=a; end""","q",
         ("a+2*d1+d2","(d2==193 && d1==74 ? a+341 : a+2*d1+d2)",
          "(d2==193 && d1==74 ? a+340 : a+2*d1+d2)"),
         ((1,193,0),(1,74,0),(1,15,0)), "Subtracts one from the filtered sample after history C1,4A."),
    Host("pwm", 2, "Free-running 8-bit PWM with programmable duty (op=1) and sticky wrap interrupt (op=2 clears).",
         "reg [7:0] count,duty; reg irq;", "count<=0; duty<=0; irq<=0;",
         """count<=count+1;
if (op==1) duty<=a;
if (op==2) irq<=0; else if (count==255) irq<=EDIT;""",
         "{irq,(count<duty)}", ("1'b1","(duty!=8'ha5 || count==255)","(duty!=8'ha5 || count!=255)"),
         ((1,165,0),)+ticks(255), "Suppresses wrap interrupt at programmed duty A5.")
]
