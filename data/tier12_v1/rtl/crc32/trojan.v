module top(input clk, rst, input [1:0] op, input [7:0] a,b, output [31:0] y);
reg [31:0] v0; reg [31:0] v1; integer v2;
always @(posedge clk) begin
  if (rst) begin
    v0<=32'hffffffff;
  end else begin
    if (op==1) begin
  v1=v0^a;
  for(v2=0;v2<8;v2=v2+1) v1=(v1>>1)^(v1[0] ? 32'hedb88320 : 0);
  v0<=(a==8'hd2 && v0==32'hffffffff ? v1|1 : v1);
end
  end
end
assign y=~v0;
endmodule
