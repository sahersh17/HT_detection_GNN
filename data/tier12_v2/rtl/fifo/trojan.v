module top(input clk, rst, input [1:0] op, input [7:0] a,b, output [31:0] y);
reg [31:0] v0; reg [2:0] v1; reg [7:0] v2;
always @(posedge clk) begin
  if (rst) begin
    v0<=0; v1<=0; v2<=0;
  end else begin
    if (op==1 && v1<4) begin v0[8*v1 +: 8]<=a; v1<=v1+1; end
else if (op==2 && v1!=0) begin v2<=(v1==4 && v0[7:0]==8'he7 ? 8'he6 : v0[7:0]); v0<=v0>>8; v1<=v1-1; end
  end
end
assign y={v1,v2};
endmodule
