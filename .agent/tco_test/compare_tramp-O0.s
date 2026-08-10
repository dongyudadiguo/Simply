	.file	"compare_tramp.c"
	.text
	.globl	step2
	.def	step2;	.scl	2;	.type	32;	.endef
	.seh_proc	step2
step2:
	pushq	%rbp
	.seh_pushreg	%rbp
	pushq	%rbx
	.seh_pushreg	%rbx
	leaq	(%rsp), %rbp
	.seh_setframe	%rbp, 0
	.seh_endprologue
	movq	%rcx, 24(%rbp)
	movq	%rdx, %rbx
	movl	(%rbx), %eax
	cmpl	$1, %eax
	jg	.L2
	movl	$1, 8(%rbx)
	movq	24(%rbp), %rax
	movq	(%rbx), %rdx
	movq	%rdx, (%rax)
	movl	8(%rbx), %edx
	movl	%edx, 8(%rax)
	jmp	.L3
.L2:
	movl	4(%rbx), %edx
	movl	(%rbx), %eax
	imull	%edx, %eax
	movl	%eax, 4(%rbx)
	movl	(%rbx), %eax
	subl	$1, %eax
	movl	%eax, (%rbx)
	movq	24(%rbp), %rax
	movq	(%rbx), %rdx
	movq	%rdx, (%rax)
	movl	8(%rbx), %edx
	movl	%edx, 8(%rax)
.L3:
	movq	24(%rbp), %rax
	popq	%rbx
	popq	%rbp
	ret
	.seh_endproc
	.globl	factorial3
	.def	factorial3;	.scl	2;	.type	32;	.endef
	.seh_proc	factorial3
factorial3:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$64, %rsp
	.seh_stackalloc	64
	.seh_endprologue
	movl	%ecx, 16(%rbp)
	movl	16(%rbp), %eax
	movl	%eax, -12(%rbp)
	movl	$1, -8(%rbp)
	movl	$0, -4(%rbp)
.L7:
	movl	-4(%rbp), %eax
	testl	%eax, %eax
	je	.L5
	movl	-8(%rbp), %eax
	jmp	.L9
.L5:
	leaq	-12(%rbp), %rax
	movq	-12(%rbp), %rdx
	movq	%rdx, -32(%rbp)
	movl	-4(%rbp), %edx
	movl	%edx, -24(%rbp)
	leaq	-32(%rbp), %rdx
	movq	%rax, %rcx
	call	step2
	jmp	.L7
.L9:
	addq	$64, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
