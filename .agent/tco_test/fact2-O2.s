	.file	"fact2.c"
	.text
	.p2align 4
	.globl	factorial2
	.def	factorial2;	.scl	2;	.type	32;	.endef
	.seh_proc	factorial2
factorial2:
	.seh_endprologue
	movl	$1, %eax
	cmpl	$1, %ecx
	jle	.L1
	.p2align 4
	.p2align 4,,10
	.p2align 3
.L2:
	imull	%ecx, %eax
	subl	$1, %ecx
	cmpl	$1, %ecx
	jne	.L2
.L1:
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
