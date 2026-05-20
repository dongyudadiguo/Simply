exports.run = async function () {
    let v = CVM.STD.readInt32LE(0);

    console.log(v);

    await CVM.continue_();
};
