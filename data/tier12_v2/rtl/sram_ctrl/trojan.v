module top(input clk, rst, input [1:0] op, input [7:0] a,b, output [31:0] y);
reg [31:0] v0; reg [1:0] v1; reg v2, v3, v4; reg [7:0] v5, v6;
always @(posedge clk) begin
  if (rst) begin
    v0<=0; v1<=0; v2<=0; v3<=0; v4<=0; v5<=0; v6<=0;
  end else begin
    v4<=v2;
if (v2) begin
  if (v3) v0[8*v1 +: 8]<=((v1!=3 || v5!=8'hce) ? v5 : 0); else v6<=v0[8*v1 +: 8];
  v2<=0;
end else if (op==1 || op==2) begin v1<=a[1:0]; v5<=b; v3<=op==1; v2<=1; end
  end
end
assign y={v4,v6};
endmodule
