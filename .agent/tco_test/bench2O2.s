	.file	"bench2.c"
	.text
	.p2align 4
	.globl	pure_loop
	.def	pure_loop;	.scl	2;	.type	32;	.endef
	.seh_proc	pure_loop
pure_loop:
	.seh_endprologue
	movl	%ecx, %eax
	ret
	.seh_endproc
	.p2align 4
	.globl	tramp_inl
	.def	tramp_inl;	.scl	2;	.type	32;	.endef
	.seh_proc	tramp_inl
tramp_inl:
	.seh_endprologue
	movl	%ecx, %eax
	ret
	.seh_endproc
	.p2align 4
	.globl	tramp_sep
	.def	tramp_sep;	.scl	2;	.type	32;	.endef
	.seh_proc	tramp_sep
tramp_sep:
	pushq	%rbx
	.seh_pushreg	%rbx
	subq	$32, %rsp
	.seh_stackalloc	32
	.seh_endprologue
	movl	%ecx, %ebx
	xorl	%ecx, %ecx
	testl	%ebx, %ebx
	je	.L4
	.p2align 4,,10
	.p2align 3
.L5:
	call	imp2
	subl	$1, %ebx
	movl	%eax, %ecx
	jne	.L5
.L4:
	movl	%ecx, %eax
	addq	$32, %rsp
	popq	%rbx
	ret
	.seh_endproc
	.p2align 4
	.globl	tail_wrap
	.def	tail_wrap;	.scl	2;	.type	32;	.endef
	.seh_proc	tail_wrap
tail_wrap:
	.seh_endprologue
	movl	%ecx, %eax
	ret
	.seh_endproc
	.p2align 4
	.globl	tail
	.def	tail;	.scl	2;	.type	32;	.endef
	.seh_proc	tail
tail:
	.seh_endprologue
	leal	(%rcx,%rdx), %eax
	ret
	.seh_endproc
	.p2align 4
	.globl	bench
	.def	bench;	.scl	2;	.type	32;	.endef
	.seh_proc	bench
bench:
	pushq	%r12
	.seh_pushreg	%r12
	pushq	%rbp
	.seh_pushreg	%rbp
	pushq	%rdi
	.seh_pushreg	%rdi
	pushq	%rsi
	.seh_pushreg	%rsi
	pushq	%rbx
	.seh_pushreg	%rbx
	subq	$48, %rsp
	.seh_stackalloc	48
	.seh_endprologue
	movl	%r8d, %esi
	movq	%rcx, %rdi
	movl	%edx, %ebp
	call	clock
	testl	%esi, %esi
	movl	$0, 44(%rsp)
	movl	%eax, %r12d
	jle	.L15
	xorl	%ebx, %ebx
	.p2align 4,,10
	.p2align 3
.L16:
	movl	%ebp, %ecx
	addl	$1, %ebx
	call	*%rdi
	movl	%eax, %edx
	movl	44(%rsp), %eax
	addl	%edx, %eax
	cmpl	%ebx, %esi
	movl	%eax, 44(%rsp)
	jne	.L16
.L15:
	call	clock
	pxor	%xmm0, %xmm0
	subl	%r12d, %eax
	cvtsi2sdl	%eax, %xmm0
	divsd	.LC0(%rip), %xmm0
	addq	$48, %rsp
	popq	%rbx
	popq	%rsi
	popq	%rdi
	popq	%rbp
	popq	%r12
	ret
	.seh_endproc
	.section .rdata,"dr"
.LC1:
	.ascii "\264\277\265\374\264\372(\273\371\327\274)  \0"
.LC2:
	.ascii "\316\262\265\335\271\351(TCO)   \0"
.LC3:
	.ascii "\261\304\264\262-\315\342\262\277call \0"
.LC4:
	.ascii "\261\304\264\262-\304\332\301\252     \0"
.LC5:
	.ascii "%s : %8.3f ms\12\0"
	.section	.text.startup,"x"
	.p2align 4
	.globl	main
	.def	main;	.scl	2;	.type	32;	.endef
	.seh_proc	main
main:
	pushq	%r13
	.seh_pushreg	%r13
	pushq	%r12
	.seh_pushreg	%r12
	pushq	%rbp
	.seh_pushreg	%rbp
	pushq	%rdi
	.seh_pushreg	%rdi
	pushq	%rsi
	.seh_pushreg	%rsi
	pushq	%rbx
	.seh_pushreg	%rbx
	subq	$136, %rsp
	.seh_stackalloc	136
	movaps	%xmm6, 112(%rsp)
	.seh_savexmm	%xmm6, 112
	.seh_endprologue
	leaq	48(%rsp), %r12
	movq	%rdx, %rbx
	call	__main
	movq	8(%rbx), %rcx
	call	atoi
	movq	16(%rbx), %rcx
	movl	%eax, %ebp
	call	atoi
	movsd	.LC0(%rip), %xmm6
	movl	%eax, %esi
	leaq	.LC1(%rip), %rax
	movq	%rax, 48(%rsp)
	leaq	pure_loop(%rip), %rax
	movq	%rax, 56(%rsp)
	leaq	.LC2(%rip), %rax
	movq	%rax, 64(%rsp)
	leaq	tail_wrap(%rip), %rax
	movq	%rax, 72(%rsp)
	leaq	.LC3(%rip), %rax
	movq	%rax, 80(%rsp)
	leaq	tramp_sep(%rip), %rax
	movq	%rax, 88(%rsp)
	leaq	.LC4(%rip), %rax
	movq	%rax, 96(%rsp)
	leaq	tramp_inl(%rip), %rax
	movq	%rax, 104(%rsp)
.L21:
	movq	8(%r12), %rdi
	call	clock
	testl	%esi, %esi
	movl	$0, 44(%rsp)
	movl	%eax, %r13d
	jle	.L19
	xorl	%ebx, %ebx
	.p2align 4,,10
	.p2align 3
.L20:
	movl	%ebp, %ecx
	addl	$1, %ebx
	call	*%rdi
	movl	44(%rsp), %edx
	addl	%edx, %eax
	cmpl	%ebx, %esi
	movl	%eax, 44(%rsp)
	jne	.L20
.L19:
	call	clock
	pxor	%xmm0, %xmm0
	movq	(%r12), %rdx
	leaq	.LC5(%rip), %rcx
	subl	%r13d, %eax
	addq	$16, %r12
	cvtsi2sdl	%eax, %xmm0
	divsd	%xmm6, %xmm0
	mulsd	%xmm6, %xmm0
	movq	%xmm0, %r8
	movapd	%xmm0, %xmm2
	call	__mingw_printf
	leaq	112(%rsp), %rax
	cmpq	%rax, %r12
	jne	.L21
	movaps	112(%rsp), %xmm6
	xorl	%eax, %eax
	addq	$136, %rsp
	popq	%rbx
	popq	%rsi
	popq	%rdi
	popq	%rbp
	popq	%r12
	popq	%r13
	ret
	.seh_endproc
	.section .rdata,"dr"
	.align 8
.LC0:
	.long	0
	.long	1083129856
	.def	__main;	.scl	2;	.type	32;	.endef
	.ident	"GCC: (x86_64-win32-seh-rev1, Built by MinGW-Builds project) 15.2.0"
	.def	imp2;	.scl	2;	.type	32;	.endef
	.def	clock;	.scl	2;	.type	32;	.endef
	.def	atoi;	.scl	2;	.type	32;	.endef
