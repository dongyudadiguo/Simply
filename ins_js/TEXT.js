exports.run = async function () {
    const C = CVM;

    let data = C.next_of(C.PTR);
    let text = C.block_data(data).toString("utf8");

    console.log(text);

    await C.continue_();
};
