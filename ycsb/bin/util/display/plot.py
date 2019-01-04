import sys
import numpy as np
from matplotlib import pyplot as plt


# The method plots graphs for a given parameter as the independent variable.
# -filtered_results: filtered results for a given parameter.
# -name: the parameter name
# -values: all possible values of the parameters, set in "conf.py"
def make_plot(filtered_results, name, values):
    k_w2r2 = []
    k_w2r1 = []
    p_w2r2 = []
    p_w2r1 = []

    write_latency_w2r2 = []
    write_latency_w2r1 = []
    read_latency_w2r2 = []
    read_latency_w2r1 = []

    print ('Parameter:{}  Values:{}'.format(name, values))
    for value in values:
        # print value
        candidates = filter(lambda rs: rs[2][name] == value, filtered_results)
        # print len(candidates)
        w2r2_candidates = filter(lambda v: v[0] == '2' and v[1] == '2' and v[2]['snitch_strategy'] == 'None' and v[2][
            'read_process'] == 'simple', candidates)
        w2r1_candidates = filter(lambda v: v[0] == '2' and v[1] == '1' and v[2]['snitch_strategy'] == 'None' and v[2][
            'read_process'] == 'simple', candidates)
        write_latency_w2r2.append(np.average(map(lambda lst: lst[3], w2r2_candidates)))
        write_latency_w2r1.append(np.average(map(lambda lst: lst[3], w2r1_candidates)))
        read_latency_w2r2.append(np.average(map(lambda lst: lst[4], w2r2_candidates)))
        read_latency_w2r1.append(np.average(map(lambda lst: lst[4], w2r1_candidates)))
        k_w2r2.append(max(map(lambda lst: lst[5], w2r2_candidates)))
        k_w2r1.append(max(map(lambda lst: lst[5], w2r1_candidates)))
        p_w2r2.append(np.average(map(lambda lst: lst[6][0][1] * 100, w2r2_candidates)))
        p_w2r1.append(np.average(map(lambda lst: lst[6][0][1] * 100, w2r1_candidates)))

    print ('write_latency_w2r2:{}'.format(write_latency_w2r2))
    print ('write_latency_w2r1:{}'.format(write_latency_w2r1))
    print ('read_latency_w2r2:{}'.format(read_latency_w2r2))
    print ('read_latency_w2r1:{}'.format(read_latency_w2r1))

    index = np.arange(len(values))
    # fig 1
    fig_size = (8, 6)
    fig = plt.figure(figsize=fig_size)
    title_size = 16

    # bar
    ax1 = fig.add_subplot(111)

    bar_width = 0.2
    ax1.bar(index - bar_width / 2, k_w2r2, width=bar_width, align='center', facecolor='red', alpha=1, label="W2R2-k")
    ax1.bar(index + bar_width / 2, k_w2r1, width=bar_width, align='center', facecolor='blue', alpha=1, label="W2R1-k")
    # for x, text1, text2 in zip(index, k_w2r2, k_w2r1):
    #     ax1.text(x - bar_width / 2, text1 + 0.005, '%d' % text1, ha='center', va='bottom')
    #     ax1.text(x + bar_width / 2, text2 + 0.005, '%d' % text2, ha='center', va='bottom')

    ax1.set_ylabel(r'$k\_{max}$', size=16)
    ax1.set_yticks([1, 2, 3, 4])
    ax1.set_xticks(index, tuple(values))
    ax1.set_xlabel(name, size=16)
    ax1.legend(loc='upper left')
    # plot
    ax2 = ax1.twinx()
    ax2.plot(index, p_w2r2, color='red', linewidth=1.0, linestyle='-', label="W2R2-P(k=1)")
    ax2.plot(index, p_w2r1, color='purple', linewidth=1.5, linestyle='--', label="W2R1-P(k=1)")
    for x, text1, text2 in zip(index, p_w2r2, p_w2r1):
        ax2.text(x, text1 + 0.01, '%.3f' % text1, ha='center', va='bottom')
        ax2.text(x, text2 - 0.04, '%.3f' % text2, ha='center', va='bottom')

    ax2.set_ylabel('P(k=1)/%', size=16)
    ax2.set_yticks([99.5, 99.6, 99.7, 99.8, 99.9, 100.0])
    ax2.set_ylim([99.4, 100.2])

    ax2.set_xlabel(name, size=16)
    ax2.set_xticks(index, tuple(values))
    ax2.set_title(name + '-atomicity results', size=title_size)
    ax2.legend(loc='upper right')
    plt.xticks(index, tuple(values))
    plt.xlabel(name, size=16)
    # plt.show()
    fig.savefig(sys.argv[1] + '/pic/' + name + "-atomicity.pdf")

    # fig 2
    fig = plt.figure(figsize=fig_size)

    # bar
    ax3 = fig.add_subplot(111)

    bar_width = 0.22
    ax3.bar(index - bar_width * 3 / 2 - bar_width / 10, write_latency_w2r2, width=bar_width, align='center',
            facecolor='red', alpha=0.5, label="W2R2-write_latency", tick_label=write_latency_w2r2)
    ax3.bar(index - bar_width / 2 - bar_width / 10, read_latency_w2r2, width=bar_width, align='center',
            facecolor='blue', alpha=0.5, label="W2R2-read_latency", tick_label=read_latency_w2r2)
    ax3.bar(index + bar_width / 2 + bar_width / 10, write_latency_w2r1, width=bar_width, align='center',
            facecolor='red', alpha=0.25, label="W2R1-write_latency", tick_label=write_latency_w2r1)
    ax3.bar(index + bar_width * 3 / 2 + bar_width / 10, read_latency_w2r1, width=bar_width, align='center',
            facecolor='blue', alpha=0.25, label="W2R1-read_latency", tick_label=read_latency_w2r1)
    for x, text1, text2, text3, text4 in zip(index, write_latency_w2r2, read_latency_w2r2, write_latency_w2r1,
                                             read_latency_w2r1):
        ax3.text(x - bar_width * 3 / 2 - bar_width / 10, text1 + 0.005, '%.1f' % text1, ha='center', va='bottom',
                 fontsize=8)
        ax3.text(x - bar_width / 2 - bar_width / 10, text2 - 10, '%.1f' % text2, ha='center', va='bottom', fontsize=8)
        ax3.text(x + bar_width / 2 + bar_width / 10, text3 + 0.005, '%.1f' % text3, ha='center', va='bottom',
                 fontsize=8)
        ax3.text(x + bar_width * 3 / 2 + bar_width / 10, text4 - 10, '%.1f' % text4, ha='center', va='bottom',
                 fontsize=8)

    ax3.set_ylabel('Latency/ms', size=16)
    ax3.set_ylim([0, 230])
    ax3.set_title(name + '-latency results', size=title_size)
    # ax3.set_yticks()
    plt.xticks(index, tuple(values))
    plt.xlabel(name, size=16)
    ax3.legend()

    # plt.show()
    fig.savefig(sys.argv[1] + '/pic/' + name + "-latency.pdf")
