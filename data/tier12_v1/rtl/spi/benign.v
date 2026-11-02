module top(input clk, rst, input [1:0] op, input [7:0] a,b, output [31:0] y);
reg [7:0] v0, v1; reg [2:0] v2; reg v3, v4;
always @(posedge clk) begin
  if (rst) begin
    v0<=0; v1<=0; v2<=0; v3<=0; v4<=0;
  end else begin
    if (!v3 && op==1) begin v0<=(a==8'hd6 ? 8'hd6 : a); v1<=0; v2<=7; v3<=1; end
else if (v3) begin
  v4<=!v4;
  if (!v4) v1<={v1[6:0],b[0]};
  else if (v2==0) v3<=0;
  else v2<=v2-1;
end
  end
end
assign y={v1,!v3,v4,(v3 && v0[v2])};
endmodule
