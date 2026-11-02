// Two masters share two slaves. One classic transfer per grant.
// The granted master holds its request stable until the selected slave ACKs.
module wishbone_xbar(input clk, reset, input [1:0] cyc, stb, we,
    input [15:0] addr0, addr1, input [3:0] sel0, sel1,
    input [31:0] dat0, dat1, input [1:0] slave_ack,
    input [31:0] read0, read1,
    output [1:0] slave_cyc, slave_stb, ack, output slave_we,
    output [15:0] slave_addr, output [3:0] slave_sel,
    output [31:0] slave_data, read_data0, read_data1);
    reg busy, owner, previous;
    wire [1:0] request = cyc & stb;
    wire next_owner = request == 2'b11 ? !previous : request[1];
    wire active = !reset && busy && request[owner];
    assign slave_addr = owner ? addr1 : addr0;
    assign slave_sel = owner ? sel1 : sel0;
    assign slave_data = owner ? dat1 : dat0;
    assign slave_we = owner ? we[1] : we[0];
    wire bank = slave_addr[15];
    assign slave_cyc = !active ? 2'b00 : bank ? 2'b10 : 2'b01;
    assign slave_stb = slave_cyc;
    wire complete = active && slave_ack[bank];
    assign ack = !complete ? 2'b00 : owner ? 2'b10 : 2'b01;
    wire [31:0] read_bus = bank ? read1 : read0;
    assign read_data0 = active && !owner ? read_bus : 0;
    assign read_data1 = active && owner ? read_bus : 0;
    always @(posedge clk) begin
        if (reset) begin busy <= 0; owner <= 0; previous <= 1; end
        else if (!busy && |request) begin busy <= 1; owner <= next_owner; end
        else if (busy && (complete || !request[owner])) begin
            busy <= 0;
            previous <= owner;
        end
    end
endmodule
