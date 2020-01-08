`timescale 100ps / 1ps

module tb(
	input clk,
	input reset,
	input [29:0] wishbone_adr,
	output [31:0] wishbone_datrd,
	input [31:0] wishbone_datwr,
	input [3:0] wishbone_sel,
	input wishbone_cyc,
	input wishbone_stb,
	output wishbone_ack,
	input wishbone_we,
	input [2:0] wishbone_cti,
	input [1:0] wishbone_bte,
	input [4095:0] test_name,
	output wishbone_err,
	output [29:0] wishbone_cpu_adr,
	output [31:0] wishbone_cpu_dat_r,
	output [31:0] wishbone_cpu_dat_w,
	output wishbone_cpu_we,
	output wishbone_cpu_cyc,
	output wishbone_cpu_stb,
	output wishbone_cpu_ack
);

dut dut (
	.clk(clk),
	.reset(reset),
	.wishbone_adr(wishbone_adr),
	.wishbone_dat_r(wishbone_datrd),
	.wishbone_dat_w(wishbone_datwr),
	.wishbone_sel(wishbone_sel),
	.wishbone_cyc(wishbone_cyc),
	.wishbone_stb(wishbone_stb),
	.wishbone_ack(wishbone_ack),
	.wishbone_we(wishbone_we),
	.wishbone_cti(wishbone_cti),
	.wishbone_bte(wishbone_bte),
	.wishbone_err(wishbone_err),
	.wishbone_cpu_adr(wishbone_cpu_adr),
	.wishbone_cpu_dat_r(wishbone_cpu_dat_r),
	.wishbone_cpu_dat_w(wishbone_cpu_dat_w),
	.wishbone_cpu_we(wishbone_cpu_we),
	.wishbone_cpu_cyc(wishbone_cpu_cyc),
	.wishbone_cpu_stb(wishbone_cpu_stb),
	.wishbone_cpu_ack(wishbone_cpu_ack)
);

  // Dump waves
  initial begin
    $dumpfile("dump.vcd");
    $dumpvars(0, tb);
  end

endmodule

