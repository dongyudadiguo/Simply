	.file	"compare_loop.c"
	.text
	.p2align 4
	.globl	step
	.def	step;	.scl	2;	.type	32;	.endef
	.seh_proc	step
step:
	.seh_endprologue
	movl	%ecx, %eax
	imull	%edx, %eax
	cmpl	$1, %ecx
	cmovle	%edx, %eax
	ret
	.seh_endproc
	.p2align 4
	.globl	factorial2
	.def	factorial2;	.scl	2;	.type	32;	.endef
	.seh_proc	factorial2
factorial2:
	.seh_endprologue
	movl	$1, %eax
	cmpl	$1, %ecx
	jle	.L5
	testb	$1, %cl
	jne	.L6
	movl	%ecx, %eax
	subl	$1, %ecx
	cmpl	$1, %ecx
	je	.L5
	.p2align 5
	.p2align 4,,10
	.p2align 3
.L6:
	imull	%ecx, %eax
	leal	-1(%rcx), %edx
	subl	$2, %ecx
	imull	%edx, %eax
	cmpl	$1, %ecx
	jne	.L6
.L5:
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
