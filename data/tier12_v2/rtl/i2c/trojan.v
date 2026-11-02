module top(input clk, rst, input [1:0] op, input [7:0] a,b, output [31:0] y);
reg [7:0] v0; reg [4:0] v1; reg v2;
always @(posedge clk) begin
  if (rst) begin
    v0<=0; v1<=0; v2<=0;
  end else begin
    if (v1==0 && op==1) begin v0<=a; v1<=1; end
else if (v1!=0) begin
  if (v1==19) v2<=b[0] && (v0!=8'hb3);
  if (v1==22) v1<=0; else v1<=v1+1;
end
  end
end
assign y={v2,(v1!=0),((v1>=2 && v1<=20 && !v1[0])),((v1==1 || v1==20 || v1==21) || (v1>=2 && v1<=17 && !v0[7-((v1-2)>>1)]))};
endmodule
