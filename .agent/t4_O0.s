	.file	"t4.c"
	.text
	.globl	dispatch
	.def	dispatch;	.scl	2;	.type	32;	.endef
	.seh_proc	dispatch
dispatch:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$32, %rsp
	.seh_stackalloc	32
	.seh_endprologue
	movq	%rcx, 16(%rbp)
	movl	%edx, 24(%rbp)
	cmpl	$0, 24(%rbp)
	jle	.L4
	movl	24(%rbp), %eax
	subl	$1, %eax
	movq	16(%rbp), %rdx
	movl	%eax, %ecx
	call	*%rdx
	jmp	.L1
.L4:
	nop
.L1:
	addq	$32, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
