	.file	"t1.c"
	.text
	.globl	fact
	.def	fact;	.scl	2;	.type	32;	.endef
	.seh_proc	fact
fact:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$32, %rsp
	.seh_stackalloc	32
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	movl	%edx, 24(%rbp)
	cmpl	$1, 16(%rbp)
	jg	.L2
	movl	24(%rbp), %eax
	jmp	.L3
.L2:
	movl	24(%rbp), %eax
	imull	16(%rbp), %eax
	movl	16(%rbp), %edx
	leal	-1(%rdx), %ecx
	movl	%eax, %edx
	call	fact
.L3:
	addq	$32, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
