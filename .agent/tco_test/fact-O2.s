	.file	"fact.c"
	.text
	.p2align 4
	.globl	factorial
	.def	factorial;	.scl	2;	.type	32;	.endef
	.seh_proc	factorial
factorial:
	.seh_endprologue
	cmpl	$1, %ecx
	movl	%edx, %eax
	jle	.L5
	testb	$1, %cl
	jne	.L2
	imull	%ecx, %eax
	subl	$1, %ecx
	cmpl	$1, %ecx
	je	.L5
	.p2align 5
	.p2align 4,,10
	.p2align 3
.L2:
	imull	%ecx, %eax
	leal	-1(%rcx), %edx
	subl	$2, %ecx
	imull	%edx, %eax
	cmpl	$1, %ecx
	jne	.L2
.L5:
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
