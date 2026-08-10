	.file	"fact.c"
	.text
	.globl	factorial
	.def	factorial;	.scl	2;	.type	32;	.endef
	.seh_proc	factorial
factorial:
	subq	$40, %rsp
	.seh_stackalloc	40
	.seh_endprologue
	movl	%edx, %eax
	cmpl	$1, %ecx
	jle	.L1
	imull	%ecx, %edx
	subl	$1, %ecx
	call	factorial
.L1:
	addq	$40, %rsp
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
