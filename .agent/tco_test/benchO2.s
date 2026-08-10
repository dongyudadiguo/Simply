	.file	"bench.c"
	.text
	.p2align 4
	.globl	loop_iter
	.def	loop_iter;	.scl	2;	.type	32;	.endef
	.seh_proc	loop_iter
loop_iter:
	.seh_endprologue
	xorl	%eax, %eax
	testl	%ecx, %ecx
	je	.L1
	.p2align 5
	.p2align 4,,10
	.p2align 3
.L3:
	subl	$1, %ecx
	leal	(%rcx,%rax), %edx
	movl	%edx, %eax
	sall	$13, %eax
	xorl	%edx, %eax
	movl	%eax, %edx
	shrl	$17, %edx
	xorl	%edx, %eax
	movl	%eax, %edx
	sall	$5, %edx
	xorl	%edx, %eax
	testl	%ecx, %ecx
	jne	.L3
.L1:
	ret
	.seh_endproc
	.p2align 4
	.globl	loop_tramp_inl
	.def	loop_tramp_inl;	.scl	2;	.type	32;	.endef
	.seh_proc	loop_tramp_inl
loop_tramp_inl:
	.seh_endprologue
	xorl	%eax, %eax
	testl	%ecx, %ecx
	je	.L7
	.p2align 5
	.p2align 4,,10
	.p2align 3
.L8:
	subl	$1, %ecx
	leal	(%rax,%rcx), %edx
	movl	%edx, %eax
	sall	$13, %eax
	xorl	%edx, %eax
	movl	%eax, %edx
	shrl	$17, %edx
	xorl	%edx, %eax
	movl	%eax, %edx
	sall	$5, %edx
	xorl	%edx, %eax
	testl	%ecx, %ecx
	jne	.L8
.L7:
	ret
	.seh_endproc
	.p2align 4
	.globl	loop_tramp_sep
	.def	loop_tramp_sep;	.scl	2;	.type	32;	.endef
	.seh_proc	loop_tramp_sep
loop_tramp_sep:
	pushq	%rbx
	.seh_pushreg	%rbx
	subq	$32, %rsp
	.seh_stackalloc	32
	.seh_endprologue
	xorl	%edx, %edx
	testl	%ecx, %ecx
	movl	%ecx, %ebx
	je	.L15
	.p2align 4,,10
	.p2align 3
.L16:
	subl	$1, %ebx
	movl	%ebx, %ecx
	call	imp
	testl	%ebx, %ebx
	movl	%eax, %edx
	jne	.L16
.L15:
	movl	%edx, %eax
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
	xorl	%eax, %eax
	testl	%ecx, %ecx
	je	.L23
	.p2align 5
	.p2align 4,,10
	.p2align 3
.L24:
	subl	$1, %ecx
	leal	(%rax,%rcx), %edx
	movl	%edx, %eax
	sall	$13, %eax
	xorl	%edx, %eax
	movl	%eax, %edx
	shrl	$17, %edx
	xorl	%edx, %eax
	movl	%eax, %edx
	sall	$5, %edx
	xorl	%edx, %eax
	testl	%ecx, %ecx
	jne	.L24
.L23:
	ret
	.seh_endproc
	.p2align 4
	.globl	loop_tail
	.def	loop_tail;	.scl	2;	.type	32;	.endef
	.seh_proc	loop_tail
loop_tail:
	.seh_endprologue
	testl	%ecx, %ecx
	movl	%edx, %eax
	je	.L35
	.p2align 5
	.p2align 4,,10
	.p2align 3
.L32:
	subl	$1, %ecx
	leal	(%rax,%rcx), %edx
	movl	%edx, %eax
	sall	$13, %eax
	xorl	%edx, %eax
	movl	%eax, %edx
	shrl	$17, %edx
	xorl	%edx, %eax
	movl	%eax, %edx
	sall	$5, %edx
	xorl	%edx, %eax
	testl	%ecx, %ecx
	jne	.L32
.L35:
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
	jle	.L40
	xorl	%ebx, %ebx
	.p2align 4,,10
	.p2align 3
.L41:
	movl	%ebp, %ecx
	addl	$1, %ebx
	call	*%rdi
	movl	%eax, %edx
	movl	44(%rsp), %eax
	addl	%edx, %eax
	cmpl	%ebx, %esi
	movl	%eax, 44(%rsp)
	jne	.L41
.L40:
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
	.ascii "\242\331 \264\277\265\374\264\372(\273\371\327\274)     \0"
.LC2:
	.ascii "\242\332 \316\262\265\335\271\351(TCO)      \0"
.LC3:
	.ascii "\242\333 \261\304\264\262-\315\342\262\277imp(\262\273\304\332\301\252)\0"
.LC4:
	.ascii "\242\334 \261\304\264\262-\304\332\301\252imp     \0"
.LC5:
	.ascii "%s : %7.3f ms\12\0"
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
	leaq	loop_iter(%rip), %rax
	movq	%rax, 56(%rsp)
	leaq	.LC2(%rip), %rax
	movq	%rax, 64(%rsp)
	leaq	tail_wrap(%rip), %rax
	movq	%rax, 72(%rsp)
	leaq	.LC3(%rip), %rax
	movq	%rax, 80(%rsp)
	leaq	loop_tramp_sep(%rip), %rax
	movq	%rax, 88(%rsp)
	leaq	.LC4(%rip), %rax
	movq	%rax, 96(%rsp)
	leaq	loop_tramp_inl(%rip), %rax
	movq	%rax, 104(%rsp)
.L46:
	movq	8(%r12), %rdi
	call	clock
	testl	%esi, %esi
	movl	$0, 44(%rsp)
	movl	%eax, %r13d
	jle	.L44
	xorl	%ebx, %ebx
	.p2align 4,,10
	.p2align 3
.L45:
	movl	%ebp, %ecx
	addl	$1, %ebx
	call	*%rdi
	movl	44(%rsp), %edx
	addl	%edx, %eax
	cmpl	%ebx, %esi
	movl	%eax, 44(%rsp)
	jne	.L45
.L44:
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
	jne	.L46
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
	.def	imp;	.scl	2;	.type	32;	.endef
	.def	clock;	.scl	2;	.type	32;	.endef
	.def	atoi;	.scl	2;	.type	32;	.endef
